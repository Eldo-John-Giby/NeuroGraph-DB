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


def test_inductive_worker_scoring_and_evidence_persistence(client, reader_token, seeded_inductive_environment):
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
