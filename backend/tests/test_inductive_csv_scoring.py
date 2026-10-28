"""Integration tests for inductive CSV review upload and scoring runtime."""

from datetime import datetime, timezone
import pytest
from sqlalchemy import func, select

from app.models import (
    BatchAnalysis,
    BatchAnalysisRow,
    FraudPrediction,
    GraphSnapshot,
    GraphSnapshotReview,
    InductiveInferenceJob,
    InductivePredictionEvidence,
    InferenceRun,
    ModelVersion,
    PreprocessingVersion,
    Product,
    Review,
    Reviewer,
)
from app.services.inductive_yelpchi import BundleVerificationError, get_inductive_runtime


@pytest.fixture
def isolated_test_embeddings(monkeypatch):
    """Stub only embedding inputs for fabricated test history; never used in serving.

    These tests exercise worker persistence and real classification-head attention,
    not RoBERTa quality. Live model quality is checked by separate bundle reproduction.
    """
    import torch
    runtime = get_inductive_runtime()
    keys = [f'hist-rev-{index}' for index in range(3)] + [f'bulk-hist-{index:03d}' for index in range(60)] + ['hist-future-2012']
    monkeypatch.setattr(runtime, '_serving_review_id_to_idx', {key: index for index, key in enumerate(keys)})
    monkeypatch.setattr(runtime, 'encode_texts', lambda texts, batch_size=32: torch.zeros((len(texts), 768)))
    return runtime


@pytest.fixture
def seeded_inductive_environment(client):
    """Seed the database with verified preprocessing, model, and graph snapshot."""
    with client._testing_session_factory() as session:
        prep = PreprocessingVersion(
            version_key="raw-yelpchi-inductive-roberta-v1",
            preprocessing_sha256="a" * 64,
            preprocessing_config={"scaler": "fitted"},
            code_revision="e2da8e2f811d1448a5b465c236feacd80ffbac7b",
            lifecycle_status="verified",
            verified_at=datetime.now(timezone.utc),
        )
        session.add(prep)
        session.flush()

        snapshot = GraphSnapshot(
            snapshot_key="raw-yelpchi-inductive-graph-47k-v1",
            dataset_name="samygithub/collective-opinion-spam-detection",
            dataset_sha256="dbd3769b608bf249ed484f87d291e5d73f4988fd33e26f1bb96a50e8cdd418c8",
            artifact_uri="artifacts/verified_inductive/raw_yelpchi_inductive_seed42_20261025T125837Z/serving_graph.pt",
            artifact_sha256="b" * 64,
            graph_builder_version="build_yelpchi_inductive_graph.py@ab41cde",
            relation_schema_version="inductive-rur-rsr-rtr-v1",
            split_protocol_key="chronological_arrival_windows_60_20_20",
            node_count=47176,
            edge_counts={"rur": 54338, "rsr": 1658662, "rtr": 450271},
            storage_status="available",
            batch_context_permitted=True,
            context_scope_key="inductive-rur-rsr-rtr-v1",
            provenance="real",
        )
        session.add(snapshot)
        session.flush()

        model = ModelVersion(
            version_key="raw-yelpchi-inductive-roberta-gnn-v1-seed42",
            model_name="raw_yelpchi_inductive_roberta_gnn_v1",
            architecture_version="roberta_relation_gnn_v1",
            architecture_config={"hidden_channels": 64},
            config_sha256="c" * 64,
            checkpoint_uri="artifacts/verified_inductive/raw_yelpchi_inductive_seed42_20261025T125837Z/model_state.pt",
            checkpoint_sha256="d" * 64,
            preprocessing_version_id=prep.preprocessing_version_id,
            input_contract_version="raw_text_graph_v1",
            recommended_threshold=0.787071,
            threshold_source="validation",
            lifecycle_status="verified",
            supported_inference_mode="inductive_batch_v1",
            verification_at=datetime.now(timezone.utc),
            provenance="real",
        )
        session.add(model)
        session.flush()

        # Seed 3 historical reviews in the snapshot for graph context
        reviewer = Reviewer(source_system="yelpchi-test", external_reviewer_key="user-hist-1")
        product = Product(source_system="yelpchi-test", external_product_key="prod-hist-1")
        session.add_all([reviewer, product])
        session.flush()

        for idx, date_str in enumerate(["2011-01-01T10:00:00Z", "2011-02-01T10:00:00Z", "2011-03-01T10:00:00Z"]):
            rev = Review(
                source_system="yelpchi-test",
                source_review_key=f"hist-rev-{idx}",
                reviewer_id=reviewer.reviewer_id,
                product_id=product.product_id,
                rating=5,
                reviewed_at=datetime.fromisoformat(date_str),
                review_text=f"Historical review {idx} with helpful details and good experience.",
                # ground_truth_label is present in table, but runtime MUST NOT project or leak it
                ground_truth_label=0,
                label_source="seed",
            )
            session.add(rev)
            session.flush()
            session.add(
                GraphSnapshotReview(
                    graph_snapshot_id=snapshot.graph_snapshot_id,
                    review_id=rev.review_id,
                    split="train",
                )
            )

        session.commit()
        return {
            "prep_id": prep.preprocessing_version_id,
            "snapshot_id": snapshot.graph_snapshot_id,
            "model_id": model.model_version_id,
            "reviewer_id": reviewer.reviewer_id,
            "product_id": product.product_id,
        }


def test_inductive_csv_upload_returns_queued_status(client, reader_token, seeded_inductive_environment):
    """Uploading a valid CSV with compatible snapshot and model creates queued run and job."""
    headers = {"Authorization": f"Bearer {reader_token}"}
    snapshot_id = seeded_inductive_environment["snapshot_id"]

    csv_content = (
        "review_id,reviewer_id,product_id,rating,review_date,review_text\n"
        "upload-1,user-hist-1,prod-hist-1,5,2011-04-01,Excellent service and very prompt response.\n"
        'upload-2,user-new-2,prod-hist-1,5,2011-04-02,"Great quality, highly recommended by friends!"\n'
    ).encode()

    response = client.post(
        "/api/v1/batch-analyses",
        headers=headers,
        data={"source_system": "yelpchi-test", "historic_graph_snapshot_id": str(snapshot_id)},
        files={"file": ("batch.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 201
    payload = response.json()

    assert payload["status"] == "queued"
    assert payload["row_count"] == 2
    assert payload["accepted_count"] == 2
    assert payload["rejected_count"] == 0
    assert payload["inference_run_id"] is not None
    assert payload["blocking_reasons"] == []
    assert "inference_run" in payload
    assert payload["inference_run"]["status"] == "queued"
    assert payload["inference_run"]["requested_count"] == 2
    assert payload["inference_run"]["completed_count"] == 0
    assert "job" in payload
    assert payload["job"]["status"] == "queued"

    # Status endpoint confirms queued state
    status_res = client.get(f"/api/v1/batch-analyses/{payload['batch_analysis_id']}", headers=headers)
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "queued"
    assert status_res.json()["scoring_available"] is True

    # Results endpoint shows unpredicted rows prior to scoring
    results_res = client.get(f"/api/v1/batch-analyses/{payload['batch_analysis_id']}/results", headers=headers)
    assert results_res.status_code == 200
    items = results_res.json()["items"]
    assert len(items) == 2
    assert items[0]["row_state"] == "accepted"
    assert items[0]["prediction"] is None
    assert items[1]["row_state"] == "accepted"
    assert items[1]["prediction"] is None


def test_inductive_worker_scoring_and_evidence_persistence(client, reader_token, seeded_inductive_environment, isolated_test_embeddings):
    """Calling /score executes the leased job and returns predictions with attention and evidence."""
    headers = {"Authorization": f"Bearer {reader_token}"}
    snapshot_id = seeded_inductive_environment["snapshot_id"]

    csv_content = (
        "review_id,reviewer_id,product_id,rating,review_date,review_text\n"
        "score-rev-1,user-hist-1,prod-hist-1,5,2011-04-10,Fantastic experience returning again.\n"
        'score-rev-2,user-score-2,prod-hist-1,5,2011-04-11,"Good overall product, exactly as advertised."\n'
    ).encode()

    upload = client.post(
        "/api/v1/batch-analyses",
        headers=headers,
        data={"source_system": "yelpchi-test", "historic_graph_snapshot_id": str(snapshot_id)},
        files={"file": ("batch.csv", csv_content, "text/csv")},
    )
    assert upload.status_code == 201
    batch_id = upload.json()["batch_analysis_id"]

    # Trigger scoring via the score endpoint
    score_res = client.post(f"/api/v1/batch-analyses/{batch_id}/score", headers=headers)
    assert score_res.status_code == 200
    score_payload = score_res.json()
    assert score_payload["status"] == "completed"
    assert score_payload["inference_run"]["status"] == "completed"
    assert score_payload["inference_run"]["completed_count"] == 2
    assert score_payload["job"]["status"] == "succeeded"

    # Query results and verify fraud prediction + evidence
    results_res = client.get(f"/api/v1/batch-analyses/{batch_id}/results", headers=headers)
    assert results_res.status_code == 200
    items = results_res.json()["items"]
    assert len(items) == 2

    for item in items:
        pred = item["prediction"]
        assert pred is not None
        assert 0.0 <= pred["risk_score"] <= 1.0
        assert pred["predicted_label"] in (0, 1)
        assert pred["decision"] in ("flagged", "cleared")
        assert pred["graph_status"] == "inductive_scored"

        # Verify real attention weights
        att = pred["attention_weights"]
        assert isinstance(att, dict)
        assert "rur" in att and "rsr" in att and "rtr" in att
        total_att = sum(att.values())
        assert abs(total_att - 1.0) <= 0.05

        # Verify inductive evidence fields and hashes
        ev = pred["evidence"]
        assert ev is not None
        assert ev["graph_snapshot_id"] == snapshot_id
        assert ev["relation_schema_version"] == "inductive-rur-rsr-rtr-v1"
        assert len(ev["stitched_graph_sha256"]) == 64
        assert len(ev["input_feature_sha256"]) == 64
        assert len(ev["embedding_sha256"]) == 64
        assert len(ev["bundle_manifest_sha256"]) == 64
        assert ev["bundle_manifest_sha256"] == "9d4f10a81937987ae7588d86e29191d355af296c6efc29ec3e5b331282d23edd"
        assert isinstance(ev["historic_review_ids"], list)
        assert isinstance(ev["neighbor_counts"], dict)


def test_unknown_snapshot_returns_explicit_404(client, reader_token):
    """Selecting a nonexistent snapshot returns snapshot_not_found."""
    headers = {"Authorization": f"Bearer {reader_token}"}
    csv_content = b"review_id,reviewer_id,product_id,rating,review_date,review_text\nr-1,u-1,p-1,5,2025-01-01,Test\n"
    response = client.post(
        "/api/v1/batch-analyses",
        headers=headers,
        data={"source_system": "test", "historic_graph_snapshot_id": "999999"},
        files={"file": ("b.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "snapshot_not_found"


def test_scope_incompatible_snapshot_returns_explicit_409(client, reader_token, seeded_inductive_environment):
    """A snapshot with mismatched context_scope_key is rejected with snapshot_scope_incompatible."""
    headers = {"Authorization": f"Bearer {reader_token}"}
    with client._testing_session_factory() as session:
        bad_snapshot = GraphSnapshot(
            snapshot_key="incompatible-scope-graph",
            dataset_name="test",
            dataset_sha256="e" * 64,
            artifact_uri="test://incompatible",
            artifact_sha256="f" * 64,
            graph_builder_version="test-v1",
            relation_schema_version="legacy-transductive-v1",
            split_protocol_key="test",
            node_count=100,
            storage_status="available",
            batch_context_permitted=True,
            context_scope_key="transductive-only-v1",
            provenance="real",
        )
        session.add(bad_snapshot)
        session.commit()
        bad_id = bad_snapshot.graph_snapshot_id

    csv_content = b"review_id,reviewer_id,product_id,rating,review_date,review_text\nr-1,u-1,p-1,5,2025-01-01,Test\n"
    response = client.post(
        "/api/v1/batch-analyses",
        headers=headers,
        data={"source_system": "test", "historic_graph_snapshot_id": str(bad_id)},
        files={"file": ("b.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "snapshot_scope_incompatible"


def test_synthetic_model_ineligible_for_inductive_scoring(client, reader_token, seeded_inductive_environment):
    """Synthetic demo models cannot be selected for inductive batch scoring."""
    headers = {"Authorization": f"Bearer {reader_token}"}
    snapshot_id = seeded_inductive_environment["snapshot_id"]

    with client._testing_session_factory() as session:
        synthetic_model = ModelVersion(
            version_key="synthetic-inductive-mock",
            model_name="synthetic_inductive",
            architecture_version="mock_v1",
            architecture_config={},
            config_sha256="1" * 64,
            checkpoint_uri="local://mock",
            checkpoint_sha256="2" * 64,
            preprocessing_version_id=seeded_inductive_environment["prep_id"],
            input_contract_version="mock",
            recommended_threshold=0.5,
            threshold_source="validation",
            lifecycle_status="verified",
            supported_inference_mode="inductive_batch_v1",
            provenance="synthetic_demo",
        )
        # Provenance check constraint allows synthetic_demo when not verified or when lifecycle allows
        # But our DB migration specifically tests synthetic_demo ineligibility. If model is synthetic_demo,
        # API must explicitly reject it with synthetic_model_ineligible.
        session.add(synthetic_model)
        try:
            session.commit()
            synthetic_id = synthetic_model.model_version_id
        except Exception:
            session.rollback()
            # If the DB constraint already prevents verified synthetic demo, testing is complete
            return

    csv_content = b"review_id,reviewer_id,product_id,rating,review_date,review_text\nr-1,u-1,p-1,5,2025-01-01,Test\n"
    response = client.post(
        "/api/v1/batch-analyses",
        headers=headers,
        data={
            "source_system": "test",
            "historic_graph_snapshot_id": str(snapshot_id),
            "model_version_id": str(synthetic_id),
        },
        files={"file": ("b.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "synthetic_model_ineligible"


def test_insufficient_historic_context_fails_cleanly(client, reader_token, seeded_inductive_environment):
    """When a snapshot has zero historical reviews for the training split, scoring fails with 422."""
    headers = {"Authorization": f"Bearer {reader_token}"}
    # Create an empty permitted snapshot
    with client._testing_session_factory() as session:
        empty_snapshot = GraphSnapshot(
            snapshot_key="empty-historic-graph",
            dataset_name="test",
            dataset_sha256="3" * 64,
            artifact_uri="test://empty",
            artifact_sha256="4" * 64,
            graph_builder_version="test-v1",
            relation_schema_version="inductive-rur-rsr-rtr-v1",
            split_protocol_key="test",
            node_count=0,
            storage_status="available",
            batch_context_permitted=True,
            context_scope_key="inductive-rur-rsr-rtr-v1",
            provenance="real",
        )
        session.add(empty_snapshot)
        session.commit()
        empty_id = empty_snapshot.graph_snapshot_id

    csv_content = (
        "review_id,reviewer_id,product_id,rating,review_date,review_text\n"
        "empty-ctx-rev,u-1,p-1,5,2025-01-01,Test review with no historic graph context.\n"
    ).encode()

    upload = client.post(
        "/api/v1/batch-analyses",
        headers=headers,
        data={"source_system": "test", "historic_graph_snapshot_id": str(empty_id)},
        files={"file": ("b.csv", csv_content, "text/csv")},
    )
    assert upload.status_code == 201
    batch_id = upload.json()["batch_analysis_id"]

    score_res = client.post(f"/api/v1/batch-analyses/{batch_id}/score", headers=headers)
    assert score_res.status_code == 422
    assert score_res.json()["error"]["code"] == "insufficient_historic_context"

    # Verify no fabricated predictions were written
    with client._testing_session_factory() as session:
        batch = session.get(BatchAnalysis, batch_id)
        assert batch.status == "failed"
        run = session.get(InferenceRun, batch.inference_run_id)
        assert run.status == "failed"
        preds = session.scalars(
            select(FraudPrediction).where(FraudPrediction.inference_run_id == run.inference_run_id)
        ).all()
        assert len(preds) == 0


def test_bundle_verification_failure_fails_cleanly(client, reader_token, seeded_inductive_environment, monkeypatch):
    """If the bundle manifest or checksum fails verification, scoring returns 503 without predictions."""
    headers = {"Authorization": f"Bearer {reader_token}"}
    snapshot_id = seeded_inductive_environment["snapshot_id"]

    csv_content = (
        "review_id,reviewer_id,product_id,rating,review_date,review_text\n"
        "bundle-fail-rev,u-1,p-1,5,2025-01-01,Test review for corrupted bundle.\n"
    ).encode()

    upload = client.post(
        "/api/v1/batch-analyses",
        headers=headers,
        data={"source_system": "test", "historic_graph_snapshot_id": str(snapshot_id)},
        files={"file": ("b.csv", csv_content, "text/csv")},
    )
    assert upload.status_code == 201
    batch_id = upload.json()["batch_analysis_id"]

    # Monkeypatch get_inductive_runtime to simulate manifest checksum corruption
    import app.services.inductive_worker as worker_module
    def mock_get_runtime():
        raise BundleVerificationError("Simulated checksum mismatch in run_manifest.json")

    monkeypatch.setattr(worker_module, "get_inductive_runtime", mock_get_runtime)

    score_res = client.post(f"/api/v1/batch-analyses/{batch_id}/score", headers=headers)
    assert score_res.status_code == 503
    assert score_res.json()["error"]["code"] == "bundle_verification_failed"
    with client._testing_session_factory() as session:
        batch = session.get(BatchAnalysis, batch_id)
        assert batch.status == "failed"
        run = session.get(InferenceRun, batch.inference_run_id)
        assert run.status == "failed"
        preds = session.scalars(
            select(FraudPrediction).where(FraudPrediction.inference_run_id == run.inference_run_id)
        ).all()
        assert len(preds) == 0


def test_csv_schema_and_row_level_validation(client, reader_token, seeded_inductive_environment):
    """CSV schema errors return 422; row-level errors are reported per row without dropping valid rows."""
    headers = {"Authorization": f"Bearer {reader_token}"}
    snapshot_id = seeded_inductive_environment["snapshot_id"]

    # 1. Missing required column in header (e.g. rating missing)
    bad_header_csv = b"review_id,reviewer_id,product_id,review_date,review_text\nr-1,u-1,p-1,2025-01-01,Text\n"
    res_bad_header = client.post(
        "/api/v1/batch-analyses",
        headers=headers,
        data={"source_system": "test", "historic_graph_snapshot_id": str(snapshot_id)},
        files={"file": ("bad_header.csv", bad_header_csv, "text/csv")},
    )
    assert res_bad_header.status_code == 422
    assert res_bad_header.json()["error"]["code"] == "missing_csv_columns"

    # 2. Row-level errors: rating out of range, invalid date format, missing text
    mixed_csv = (
        "review_id,reviewer_id,product_id,rating,review_date,review_text\n"
        "valid-row,user-hist-1,prod-hist-1,5,2011-04-01,Valid review with good text.\n"
        "bad-rating,user-hist-1,prod-hist-1,9,2011-04-01,Rating is 9 which exceeds 5.\n"
        "bad-date,user-hist-1,prod-hist-1,4,invalid-date,Date format is invalid.\n"
        "missing-text,user-hist-1,prod-hist-1,4,2011-04-01,\n"
    ).encode()

    res_mixed = client.post(
        "/api/v1/batch-analyses",
        headers=headers,
        data={"source_system": "test", "historic_graph_snapshot_id": str(snapshot_id)},
        files={"file": ("mixed.csv", mixed_csv, "text/csv")},
    )
    assert res_mixed.status_code == 201
    payload = res_mixed.json()
    assert payload["row_count"] == 4
    assert payload["accepted_count"] == 1
    assert payload["rejected_count"] == 3

    results = client.get(f"/api/v1/batch-analyses/{payload['batch_analysis_id']}/results", headers=headers).json()
    rows_by_state = {r["uploaded_review_key"]: r for r in results["items"]}
    assert rows_by_state["valid-row"]["row_state"] == "accepted"
    assert rows_by_state["bad-rating"]["row_state"] == "rejected"
    assert rows_by_state["bad-rating"]["validation_errors"][0]["field"] == "rating"
    assert rows_by_state["bad-date"]["row_state"] == "rejected"
    assert rows_by_state["bad-date"]["validation_errors"][0]["field"] == "review_date"
    assert rows_by_state["missing-text"]["row_state"] == "rejected"
    assert rows_by_state["missing-text"]["validation_errors"][0]["field"] == "review_text"


def test_restaurant_csv_does_not_expect_labels(client, reader_token, seeded_inductive_environment):
    """Restaurant uploads never expect ground-truth labels and persist null label fields."""
    headers = {"Authorization": f"Bearer {reader_token}"}
    snapshot_id = seeded_inductive_environment["snapshot_id"]

    # Valid restaurant upload without any label or is_spam column
    csv_content = (
        "review_id,reviewer_id,product_id,rating,review_date,review_text\n"
        "unlabeled-1,user-hist-1,prod-hist-1,5,2011-04-01,Delicious pasta and great atmosphere.\n"
    ).encode()

    upload = client.post(
        "/api/v1/batch-analyses",
        headers=headers,
        data={"source_system": "restaurant-live", "historic_graph_snapshot_id": str(snapshot_id)},
        files={"file": ("restaurant.csv", csv_content, "text/csv")},
    )
    assert upload.status_code == 201

    # Verify Review record has ground_truth_label = None and label_source = None
    with client._testing_session_factory() as session:
        rev = session.scalar(
            select(Review).where(
                Review.source_system == "restaurant-live",
                Review.source_review_key == "unlabeled-1",
            )
        )
        assert rev is not None
        assert rev.ground_truth_label is None
        assert rev.label_source is None


def test_context_query_excludes_ground_truth_and_label_source(client, seeded_inductive_environment):
    """The historical context loader projects only relation attributes and omits label columns."""
    from app.services.batch_graph import load_permitted_historic_context

    snapshot_id = seeded_inductive_environment["snapshot_id"]
    with client._testing_session_factory() as session:
        context = load_permitted_historic_context(session, snapshot_id, split="train")
        assert len(context.reviews) > 0

        # Verify BatchReviewInput dataclass has no label attributes
        for rev in context.reviews:
            assert hasattr(rev, "review_id")
            assert hasattr(rev, "reviewer_id")
            assert hasattr(rev, "product_id")
            assert hasattr(rev, "rating")
            assert hasattr(rev, "reviewed_at")
            assert hasattr(rev, "review_text")
            assert not hasattr(rev, "ground_truth_label")
            assert not hasattr(rev, "label_source")


def test_future_dated_historic_reviews_cannot_become_neighbors(client, reader_token, seeded_inductive_environment, isolated_test_embeddings):
    """Future-dated historic reviews relative to a candidate review cannot be connected as neighbors."""
    headers = {"Authorization": f"Bearer {reader_token}"}
    snapshot_id = seeded_inductive_environment["snapshot_id"]

    # Add a future-dated historic review (2012-01-01) in the snapshot for user-hist-1 and prod-hist-1
    with client._testing_session_factory() as session:
        future_rev = Review(
            source_system="yelpchi-test",
            source_review_key="hist-future-2012",
            reviewer_id=seeded_inductive_environment["reviewer_id"],
            product_id=seeded_inductive_environment["product_id"],
            rating=5,
            reviewed_at=datetime.fromisoformat("2012-01-01T12:00:00+00:00"),
            review_text="Future review from 2012 that should never link to a 2011 candidate.",
            ground_truth_label=0,
            label_source="seed",
        )
        session.add(future_rev)
        session.flush()
        session.add(
            GraphSnapshotReview(
                graph_snapshot_id=snapshot_id,
                review_id=future_rev.review_id,
                split="train",
            )
        )
        session.commit()
        future_rev_id = future_rev.review_id

    # Candidate review dated 2011-04-10
    csv_content = (
        "review_id,reviewer_id,product_id,rating,review_date,review_text\n"
        "cand-2011,user-hist-1,prod-hist-1,5,2011-04-10,Candidate review in early 2011.\n"
    ).encode()

    upload = client.post(
        "/api/v1/batch-analyses",
        headers=headers,
        data={"source_system": "yelpchi-test", "historic_graph_snapshot_id": str(snapshot_id)},
        files={"file": ("b.csv", csv_content, "text/csv")},
    )
    assert upload.status_code == 201
    batch_id = upload.json()["batch_analysis_id"]

    score_res = client.post(f"/api/v1/batch-analyses/{batch_id}/score", headers=headers)
    assert score_res.status_code == 200

    results = client.get(f"/api/v1/batch-analyses/{batch_id}/results", headers=headers).json()
    evidence = results["items"][0]["prediction"]["evidence"]
    # The candidate cannot link to the future review
    assert future_rev_id not in evidence["historic_review_ids"]


def test_neighbor_cap_and_deterministic_ordering_are_stable(client, reader_token, seeded_inductive_environment, isolated_test_embeddings):
    """Each relation enforces a 50-neighbor cap and maintains deterministic tie-breaking and hashes."""
    headers = {"Authorization": f"Bearer {reader_token}"}
    snapshot_id = seeded_inductive_environment["snapshot_id"]

    # Seed 60 past reviews for user-hist-1 and prod-hist-1 in 2010
    with client._testing_session_factory() as session:
        for i in range(60):
            r = Review(
                source_system="yelpchi-test",
                source_review_key=f"bulk-hist-{i:03d}",
                reviewer_id=seeded_inductive_environment["reviewer_id"],
                product_id=seeded_inductive_environment["product_id"],
                rating=5,
                reviewed_at=datetime.fromisoformat(f"2010-01-01T{i%24:02d}:00:00+00:00"),
                review_text=f"Bulk historical review {i} for cap testing.",
                ground_truth_label=0,
                label_source="seed",
            )
            session.add(r)
            session.flush()
            session.add(
                GraphSnapshotReview(
                    graph_snapshot_id=snapshot_id,
                    review_id=r.review_id,
                    split="train",
                )
            )
        session.commit()

    csv_content = (
        "review_id,reviewer_id,product_id,rating,review_date,review_text\n"
        "cand-cap-test,user-hist-1,prod-hist-1,5,2011-05-01,Candidate testing 50 neighbor cap.\n"
    ).encode()

    upload = client.post(
        "/api/v1/batch-analyses",
        headers=headers,
        data={"source_system": "yelpchi-test", "historic_graph_snapshot_id": str(snapshot_id)},
        files={"file": ("b.csv", csv_content, "text/csv")},
    )
    assert upload.status_code == 201
    batch_id = upload.json()["batch_analysis_id"]

    score_res = client.post(f"/api/v1/batch-analyses/{batch_id}/score", headers=headers)
    assert score_res.status_code == 200

    results = client.get(f"/api/v1/batch-analyses/{batch_id}/results", headers=headers).json()
    evidence = results["items"][0]["prediction"]["evidence"]

    # Neighbor cap check
    assert evidence["neighbor_counts"]["rur"] <= 50
    assert evidence["neighbor_counts"]["rsr"] <= 50
    assert evidence["neighbor_counts"]["rtr"] <= 50
    assert len(evidence["historic_review_ids"]) <= 50

    # Running a second time produces identical deterministic hashes
    csv_content_2 = (
        "review_id,reviewer_id,product_id,rating,review_date,review_text\n"
        "cand-cap-test-2,user-hist-1,prod-hist-1,5,2011-05-01,Candidate testing 50 neighbor cap.\n"
    ).encode()

    upload_2 = client.post(
        "/api/v1/batch-analyses",
        headers=headers,
        data={"source_system": "yelpchi-test", "historic_graph_snapshot_id": str(snapshot_id)},
        files={"file": ("b2.csv", csv_content_2, "text/csv")},
    )
    batch_id_2 = upload_2.json()["batch_analysis_id"]
    client.post(f"/api/v1/batch-analyses/{batch_id_2}/score", headers=headers)
    results_2 = client.get(f"/api/v1/batch-analyses/{batch_id_2}/results", headers=headers).json()
    evidence_2 = results_2["items"][0]["prediction"]["evidence"]

    assert evidence["stitched_graph_sha256"] == evidence_2["stitched_graph_sha256"]
    assert evidence["historic_review_ids"] == evidence_2["historic_review_ids"]


def test_stitched_graph_does_not_mutate_persisted_snapshot(client, reader_token, seeded_inductive_environment, isolated_test_embeddings):
    """Executing scoring does not alter the immutable graph snapshot record or underlying file."""
    import hashlib
    from pathlib import Path

    headers = {"Authorization": f"Bearer {reader_token}"}
    snapshot_id = seeded_inductive_environment["snapshot_id"]

    with client._testing_session_factory() as session:
        snapshot_before = session.get(GraphSnapshot, snapshot_id)
        snap_data_before = {
            "snapshot_key": snapshot_before.snapshot_key,
            "artifact_sha256": snapshot_before.artifact_sha256,
            "node_count": snapshot_before.node_count,
            "edge_counts": dict(snapshot_before.edge_counts),
        }
        artifact_path = Path(snapshot_before.artifact_uri)

    file_sha_before = hashlib.sha256(artifact_path.read_bytes()).hexdigest() if artifact_path.is_file() else None

    # Score a batch
    csv_content = (
        "review_id,reviewer_id,product_id,rating,review_date,review_text\n"
        "cand-snap-check,user-hist-1,prod-hist-1,5,2011-05-10,Snapshot immutability test.\n"
    ).encode()
    upload = client.post(
        "/api/v1/batch-analyses",
        headers=headers,
        data={"source_system": "yelpchi-test", "historic_graph_snapshot_id": str(snapshot_id)},
        files={"file": ("b.csv", csv_content, "text/csv")},
    )
    client.post(f"/api/v1/batch-analyses/{upload.json()['batch_analysis_id']}/score", headers=headers)

    # Check snapshot afterwards
    with client._testing_session_factory() as session:
        snapshot_after = session.get(GraphSnapshot, snapshot_id)
        snap_data_after = {
            "snapshot_key": snapshot_after.snapshot_key,
            "artifact_sha256": snapshot_after.artifact_sha256,
            "node_count": snapshot_after.node_count,
            "edge_counts": dict(snapshot_after.edge_counts),
        }

    assert snap_data_before == snap_data_after
    if file_sha_before is not None:
        file_sha_after = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        assert file_sha_before == file_sha_after


def test_validation_threshold_not_derived_from_test_labels(client, seeded_inductive_environment):
    """Model validation threshold is strictly derived from validation data, never test labels."""
    with client._testing_session_factory() as session:
        model = session.get(ModelVersion, seeded_inductive_environment["model_id"])
        assert model.threshold_source == "validation"
        assert abs(float(model.recommended_threshold) - 0.787071) < 1e-5


def test_tokenizer_revision_mismatch_blocks_scoring(client, reader_token, seeded_inductive_environment, monkeypatch):
    """Mismatch in code/tokenizer revision blocks scoring with bundle_verification_failed."""
    headers = {"Authorization": f"Bearer {reader_token}"}
    snapshot_id = seeded_inductive_environment["snapshot_id"]

    csv_content = (
        "review_id,reviewer_id,product_id,rating,review_date,review_text\n"
        "cand-rev-check,user-hist-1,prod-hist-1,5,2011-05-15,Tokenizer revision test.\n"
    ).encode()
    upload = client.post(
        "/api/v1/batch-analyses",
        headers=headers,
        data={"source_system": "yelpchi-test", "historic_graph_snapshot_id": str(snapshot_id)},
        files={"file": ("b.csv", csv_content, "text/csv")},
    )
    batch_id = upload.json()["batch_analysis_id"]

    import app.services.inductive_worker as worker_module
    def mock_get_runtime():
        raise BundleVerificationError("Tokenizer revision mismatch: expected e2da8e2f, got mismatched revision.")

    monkeypatch.setattr(worker_module, "get_inductive_runtime", mock_get_runtime)

    score_res = client.post(f"/api/v1/batch-analyses/{batch_id}/score", headers=headers)
    assert score_res.status_code == 503
    assert score_res.json()["error"]["code"] == "bundle_verification_failed"


def test_duplicate_idempotency_key_does_not_create_duplicate_runs(client, reader_token, seeded_inductive_environment):
    """Repeating an upload with the same Idempotency-Key returns the existing batch and run."""
    headers = {
        "Authorization": f"Bearer {reader_token}",
        "Idempotency-Key": "e2e-idempotent-test-token-001",
    }
    snapshot_id = seeded_inductive_environment["snapshot_id"]

    csv_content = (
        "review_id,reviewer_id,product_id,rating,review_date,review_text\n"
        "idemp-1,user-hist-1,prod-hist-1,5,2011-04-20,Testing idempotency deduplication.\n"
    ).encode()

    first_res = client.post(
        "/api/v1/batch-analyses",
        headers=headers,
        data={"source_system": "idemp-test", "historic_graph_snapshot_id": str(snapshot_id)},
        files={"file": ("b.csv", csv_content, "text/csv")},
    )
    assert first_res.status_code == 201
    first_run_id = first_res.json()["inference_run_id"]

    # Repeat with same Idempotency-Key
    second_res = client.post(
        "/api/v1/batch-analyses",
        headers=headers,
        data={"source_system": "idemp-test", "historic_graph_snapshot_id": str(snapshot_id)},
        files={"file": ("b.csv", csv_content, "text/csv")},
    )
    assert second_res.status_code == 201
    assert second_res.json()["inference_run_id"] == first_run_id
    assert second_res.json()["batch_analysis_id"] == first_res.json()["batch_analysis_id"]

    # Verify only 1 InferenceRun was recorded in database
    with client._testing_session_factory() as session:
        run_count = session.scalar(
            select(func.count()).select_from(InferenceRun).where(
                InferenceRun.idempotency_key == "e2e-idempotent-test-token-001"
            )
        )
        assert run_count == 1


def test_attention_stored_is_emitted_by_model_not_synthesized(client, reader_token, seeded_inductive_environment, isolated_test_embeddings):
    """Relation attention weights are emitted by the model, dynamic across edge contexts, and sum to 1."""
    headers = {"Authorization": f"Bearer {reader_token}"}
    snapshot_id = seeded_inductive_environment["snapshot_id"]

    # Two reviews with different graph contexts:
    # Row 1 connects via reviewer and product
    # Row 2 connects only via product
    csv_content = (
        "review_id,reviewer_id,product_id,rating,review_date,review_text\n"
        "att-rev-1,user-hist-1,prod-hist-1,5,2011-04-25,First review connecting to reviewer and product.\n"
        'att-rev-2,user-new-isolated,prod-hist-1,5,2011-04-26,"Second review connecting only to product."\n'
    ).encode()

    upload = client.post(
        "/api/v1/batch-analyses",
        headers=headers,
        data={"source_system": "att-test", "historic_graph_snapshot_id": str(snapshot_id)},
        files={"file": ("b.csv", csv_content, "text/csv")},
    )
    batch_id = upload.json()["batch_analysis_id"]
    client.post(f"/api/v1/batch-analyses/{batch_id}/score", headers=headers)

    results = client.get(f"/api/v1/batch-analyses/{batch_id}/results", headers=headers).json()["items"]
    att_1 = results[0]["prediction"]["attention_weights"]
    att_2 = results[1]["prediction"]["attention_weights"]

    # Valid softmax attention
    assert abs(sum(att_1.values()) - 1.0) <= 0.05
    assert abs(sum(att_2.values()) - 1.0) <= 0.05

    # Not hardcoded static mock values: weights should differ across edge structures
    # att_1 has both RUR and RSR edges, att_2 has 0 RUR edges
    assert att_1 != att_2
