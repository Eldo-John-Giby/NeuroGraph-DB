from sqlalchemy import func, select

from app.db import get_db
from app.models import (BatchAnalysis, BatchAnalysisRow, FraudPrediction, GraphSnapshot,
                        GraphSyncJob, InferenceRun, ModelVersion, PreprocessingVersion,
                        Product, Reviewer, Review)


def test_live_and_model_status(client):
    assert client.get("/health/live").json() == {"status": "alive"}
    status = client.get("/api/v1/models/status").json()
    assert status["status"] == "available"
    assert status["inference_available"] is True
    assert status["verified_real_model_count"] == 0
    assert status["reason"] == "verified_yelpchi_baseline_ready"
    assert status["verified_baseline"]["run_id"] == "yelpchi_gnn_seed42_20261024T234034Z"


def test_model_status_and_inference_use_database_provenance(client, reader_token):
    with client._testing_session_factory() as session:
        preprocessing = PreprocessingVersion(version_key="demo-provenance-prep",
                                             preprocessing_sha256="a" * 64,
                                             code_revision="test", lifecycle_status="registered")
        session.add(preprocessing)
        session.flush()
        model = ModelVersion(version_key="synthetic-demo-model", model_name="demo",
                             architecture_version="demo-v1", architecture_config={},
                             config_sha256="b" * 64,
                             preprocessing_version_id=preprocessing.preprocessing_version_id,
                             input_contract_version="demo-v1", provenance="synthetic_demo",
                             lifecycle_status="registered")
        session.add(model)
        session.commit()
        model_id = model.model_version_id

    status = client.get("/api/v1/models/status").json()
    assert status["model_version_counts_by_provenance"] == {"synthetic_demo": 1}
    assert status["verified_real_model_count"] == 0
    response = client.post(
        "/api/v1/inference-runs",
        headers={"Authorization": f"Bearer {reader_token}", "Idempotency-Key": "demo-provenance"},
        json={"model_version_id": model_id, "graph_snapshot_id": 1, "review_ids": [1]},
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "synthetic_demo_runtime_unavailable"
    with client._testing_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(InferenceRun)) == 0


def test_verified_real_provenance_still_fails_closed_without_runtime(client, reader_token):
    from datetime import datetime, timezone

    with client._testing_session_factory() as session:
        preprocessing = PreprocessingVersion(version_key="real-provenance-prep",
                                             preprocessing_sha256="f" * 64,
                                             code_revision="test", lifecycle_status="verified")
        session.add(preprocessing)
        session.flush()
        model = ModelVersion(
            version_key="verified-real-model", model_name="neurograph", architecture_version="test-v1",
            architecture_config={}, config_sha256="1" * 64, checkpoint_uri="local://checkpoint",
            checkpoint_sha256="2" * 64, preprocessing_version_id=preprocessing.preprocessing_version_id,
            input_contract_version="test-v1", recommended_threshold=0.5,
            threshold_source="validation-run-test", lifecycle_status="verified",
            verification_at=datetime.now(timezone.utc), provenance="real",
        )
        session.add(model)
        session.commit()
        model_id = model.model_version_id

    status = client.get("/api/v1/models/status").json()
    assert status["verified_real_model_count"] == 1
    assert status["reason"] == "verified_yelpchi_baseline_ready"
    response = client.post(
        "/api/v1/inference-runs",
        headers={"Authorization": f"Bearer {reader_token}", "Idempotency-Key": "real-provenance"},
        json={"model_version_id": model_id, "graph_snapshot_id": 1, "review_ids": [1]},
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "model_runtime_unavailable"
    with client._testing_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(InferenceRun)) == 0


def test_verified_baseline_serves_the_fixed_label_free_node(client, reader_token):
    headers = {"Authorization": f"Bearer {reader_token}"}
    status = client.get("/api/v1/verified-baseline/status", headers=headers)
    assert status.status_code == 200
    assert status.json()["available"] is True
    prediction = client.post("/api/v1/verified-baseline/predict", headers=headers,
                             json={"review_ids": ["yelpchi-node-00005"]})
    assert prediction.status_code == 200
    row = prediction.json()["predictions"][0]
    assert row["review_id"] == "yelpchi-node-00005"
    assert abs(row["fraud_score"] - 0.7588716149330139) <= 0.000001
    assert row["predicted_label"] == 0


def test_synthetic_demo_model_cannot_be_verified(client):
    import pytest
    from sqlalchemy.exc import IntegrityError

    with client._testing_session_factory() as session:
        preprocessing = PreprocessingVersion(version_key="demo-constraint-prep",
                                             preprocessing_sha256="c" * 64,
                                             code_revision="test", lifecycle_status="verified")
        session.add(preprocessing)
        session.flush()
        session.add(ModelVersion(
            version_key="invalid-verified-demo", model_name="demo", architecture_version="demo-v1",
            architecture_config={}, config_sha256="d" * 64, checkpoint_uri="local://demo",
            checkpoint_sha256="e" * 64, preprocessing_version_id=preprocessing.preprocessing_version_id,
            input_contract_version="demo-v1", recommended_threshold=0.5,
            threshold_source="validation", lifecycle_status="verified",
            verification_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            provenance="synthetic_demo",
        ))
        with pytest.raises(IntegrityError):
            session.commit()


def test_readiness_reports_postgres_and_model_states_without_claiming_ready(client, monkeypatch):
    import importlib
    app_module = importlib.import_module("app.main")
    from app.main import make_engine
    monkeypatch.setattr(app_module, "make_engine", lambda: make_engine("sqlite+pysqlite:///:memory:"))
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"] == {"postgresql": "available", "verified_model": "unavailable", "neo4j": "unconfigured"}


def test_login_me_logout_revokes_session(client, reader_token):
    headers = {"Authorization": f"Bearer {reader_token}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 401


def test_refresh_rotates_and_revokes_previous_access_token(client):
    login = client.post("/api/v1/auth/login", json={"email": "reader@example.edu", "password": "correct-horse-battery"})
    prior_access = login.json()["access_token"]
    rotated = client.post("/api/v1/auth/refresh")
    assert rotated.status_code == 200
    assert rotated.json()["access_token"] != prior_access
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {prior_access}"}).status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {rotated.json()['access_token']}"}).status_code == 200


def test_source_review_pair_and_review_persistence(client, reader_token):
    headers = {"Authorization": f"Bearer {reader_token}"}
    bad = client.post("/api/v1/reviews", headers=headers, json={"source_system": "import"})
    assert bad.status_code == 422
    good = client.post("/api/v1/reviews", headers=headers, json={"review_text": "A review"})
    assert good.status_code == 201
    assert client.get("/api/v1/reviews", headers=headers).json()["items"][0]["review_id"] == good.json()["review_id"]


def test_review_list_pagination_and_source_filter(client, reader_token):
    headers = {"Authorization": f"Bearer {reader_token}"}
    client.post("/api/v1/reviews", headers=headers, json={"review_text": "local"})
    imported = client.post("/api/v1/reviews", headers=headers,
                           json={"source_system": "catalog", "source_review_key": "r-10", "review_text": "imported"})
    assert imported.status_code == 201
    response = client.get("/api/v1/reviews?source_system=catalog&limit=1&offset=0", headers=headers)
    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 1 and len(body["items"]) == 1
    assert body["items"][0]["source_review_key"] == "r-10"


def test_reviewer_and_product_lists_are_authenticated_and_paginated(client, reader_token):
    with client._testing_session_factory() as session:
        session.add_all([
            Reviewer(source_system="catalog", external_reviewer_key="reviewer-a"),
            Reviewer(source_system="catalog", external_reviewer_key="reviewer-b"),
            Product(source_system="catalog", external_product_key="product-a", display_name="A"),
            Product(source_system="catalog", external_product_key="product-b", display_name="B"),
        ])
        session.commit()

    headers = {"Authorization": f"Bearer {reader_token}"}
    reviewer_response = client.get("/api/v1/reviewers?limit=1&offset=1", headers=headers)
    assert reviewer_response.status_code == 200
    assert reviewer_response.json()["total"] == 2
    assert reviewer_response.json()["items"][0]["external_reviewer_key"] == "reviewer-b"
    assert reviewer_response.json()["limit"] == 1
    assert reviewer_response.json()["offset"] == 1

    product_response = client.get("/api/v1/products?limit=1&offset=1", headers=headers)
    assert product_response.status_code == 200
    assert product_response.json()["total"] == 2
    assert product_response.json()["items"][0]["external_product_key"] == "product-b"
    assert product_response.json()["items"][0]["display_name"] == "B"

    assert client.get("/api/v1/reviewers").status_code == 401
    assert client.get("/api/v1/products").status_code == 401
    assert client.get("/api/v1/reviewers?limit=101", headers=headers).status_code == 422
    assert client.get("/api/v1/products?offset=-1", headers=headers).status_code == 422


def test_inference_run_history_pagination_and_filters(client, reader_token):
    response = client.get("/api/v1/inference-runs?status=failed&model_version_id=9&limit=5", headers={"Authorization": f"Bearer {reader_token}"})
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 5, "offset": 0}
    invalid = client.get("/api/v1/inference-runs?status=unknown", headers={"Authorization": f"Bearer {reader_token}"})
    assert invalid.status_code == 422


def test_review_prediction_history_returns_empty_for_unscored_review(client, reader_token):
    headers = {"Authorization": f"Bearer {reader_token}"}
    review = client.post("/api/v1/reviews", headers=headers, json={"review_text": "not scored"}).json()["review_id"]
    response = client.get(f"/api/v1/reviews/{review}/predictions", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 25, "offset": 0}
    missing = client.get("/api/v1/reviews/98765/predictions", headers=headers)
    assert missing.status_code == 404


def test_review_prediction_history_fields_match_frontend_and_include_provenance(client, reader_token):
    with client._testing_session_factory() as session:
        preprocessing = PreprocessingVersion(version_key="prediction-test-prep",
                                             preprocessing_sha256="a" * 64,
                                             code_revision="test", lifecycle_status="registered")
        session.add(preprocessing)
        session.flush()
        model = ModelVersion(version_key="prediction-test-model", model_name="test-model",
                             architecture_version="v1", architecture_config={},
                             config_sha256="b" * 64,
                             preprocessing_version_id=preprocessing.preprocessing_version_id,
                             input_contract_version="test-v1", lifecycle_status="registered")
        snapshot = GraphSnapshot(snapshot_key="prediction-test-snapshot", dataset_name="test",
                                 dataset_sha256="c" * 64, artifact_uri="test://graph",
                                 artifact_sha256="d" * 64, graph_builder_version="test-v1",
                                 relation_schema_version="test-v1", split_protocol_key="test-split",
                                 node_count=1)
        session.add_all([model, snapshot])
        session.flush()
        review = Review(review_text="historical result")
        session.add(review)
        session.flush()
        run = InferenceRun(model_version_id=model.model_version_id,
                           graph_snapshot_id=snapshot.graph_snapshot_id,
                           threshold=0.42, status="completed", requested_count=1,
                           completed_count=1)
        session.add(run)
        session.flush()
        session.add(FraudPrediction(inference_run_id=run.inference_run_id,
                                    review_id=review.review_id, risk_score=0.73,
                                    predicted_label=1))
        session.commit()
        review_id = review.review_id

    response = client.get(f"/api/v1/reviews/{review_id}/predictions",
                          headers={"Authorization": f"Bearer {reader_token}"})
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["prediction_id"] > 0
    assert item["fraud_score"] == 0.73
    assert item["threshold_used"] == 0.42
    assert item["predicted_label"] == 1
    assert item["provenance"]["model_version_key"] == "prediction-test-model"
    assert item["provenance"]["preprocessing_version_key"] == "prediction-test-prep"
    assert item["provenance"]["graph_snapshot_sha256"] == "d" * 64
    assert not {"fraud_prediction_id", "risk_score", "threshold"}.intersection(item)


def test_inference_unavailable_does_not_write_run(client, reader_token):
    headers = {"Authorization": f"Bearer {reader_token}", "Idempotency-Key": "retry-1"}
    response = client.post("/api/v1/inference-runs", headers=headers,
                           json={"model_version_id": 1, "graph_snapshot_id": 1, "review_ids": [1]})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "model_unavailable"
    with client._testing_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(InferenceRun)) == 0


def test_inference_checks_requested_model_lifecycle(client, reader_token):
    with client._testing_session_factory() as session:
        preprocessing = PreprocessingVersion(version_key="test-unverified", preprocessing_sha256="a" * 64,
                                             code_revision="test", lifecycle_status="registered")
        session.add(preprocessing)
        session.flush()
        model = ModelVersion(version_key="test-registered", model_name="candidate", architecture_version="v1",
                             architecture_config={}, config_sha256="b" * 64,
                             preprocessing_version_id=preprocessing.preprocessing_version_id,
                             input_contract_version="test-v1", lifecycle_status="registered")
        session.add(model)
        session.commit()
        model_id = model.model_version_id
    response = client.post("/api/v1/inference-runs", headers={"Authorization": f"Bearer {reader_token}", "Idempotency-Key": "model-test"},
                           json={"model_version_id": model_id, "graph_snapshot_id": 1, "review_ids": [1]})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "model_unavailable"


def test_review_reader_cannot_administer_users(client, reader_token):
    response = client.post("/api/v1/users", headers={"Authorization": f"Bearer {reader_token}"},
                           json={"email": "new@example.edu", "password": "correct-horse-battery-2"})
    assert response.status_code == 403


def test_validation_error_does_not_echo_password(client):
    response = client.post("/api/v1/auth/login", json={"email": "not-an-email", "password": "sensitive"})
    assert response.status_code == 422
    assert "sensitive" not in response.text


def test_example_secret_is_not_accepted_for_authentication():
    from app.config import Settings
    assert not Settings(jwt_secret_key="replace-with-at-least-32-random-bytes").configured_jwt_secret


def test_graph_sync_jobs_validate_scope_and_report_queue_truthfully(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}", "Idempotency-Key": "sync-1"}
    review = client.post("/api/v1/reviews", headers=headers, json={"review_text": "sync test"}).json()["review_id"]
    mixed = client.post("/api/v1/graph-sync-jobs", headers=headers,
                        json={"operation": "review_upsert", "review_id": review, "graph_snapshot_id": 1})
    assert mixed.status_code == 422
    queued = client.post("/api/v1/graph-sync-jobs", headers=headers,
                         json={"operation": "review_upsert", "review_id": review})
    assert queued.status_code == 202
    repeated = client.post("/api/v1/graph-sync-jobs", headers=headers,
                           json={"operation": "review_upsert", "review_id": review})
    assert repeated.json()["deduplicated"] is True
    conflict = client.post("/api/v1/graph-sync-jobs", headers=headers,
                           json={"operation": "review_delete", "review_id": review})
    assert conflict.status_code == 409
    status = client.get("/api/v1/graph-sync/status", headers=headers)
    assert status.json()["connection_verified"] is False
    assert status.json()["queue_counts"]["queued"] == 1
    with client._testing_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(GraphSyncJob)) == 1


def test_batch_csv_persists_valid_rows_and_row_level_errors_but_does_not_fake_inference(client, reader_token):
    csv_content = (
        "review_id,reviewer_id,product_id,rating,review_date,review_text\n"
        "r-1,u-1,p-1,5,2025-01-01,Good product\n"
        "r-2,u-2,p-2,6,2025-01-02,Rating is invalid\n"
        "r-1,u-3,p-3,4,2025-01-03,Duplicate uploaded key\n"
        "r-3,u-1,p-1,3,2025-01-04,Another review\n"
    ).encode()
    response = client.post(
        "/api/v1/batch-analyses",
        headers={"Authorization": f"Bearer {reader_token}"},
        data={"source_system": "batch-test"},
        files={"file": ("reviews.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "blocked"
    assert payload["row_count"] == 4
    assert payload["accepted_count"] == 2
    assert payload["rejected_count"] == 2
    assert payload["inference_run_id"] is None
    assert "verified_model_bundle_not_registered" in payload["blocking_reasons"]
    assert "historic_graph_snapshot_not_selected" in payload["blocking_reasons"]

    headers = {"Authorization": f"Bearer {reader_token}"}
    status = client.get(f"/api/v1/batch-analyses/{payload['batch_analysis_id']}", headers=headers)
    assert status.status_code == 200
    assert status.json()["scoring_available"] is False

    results = client.get(f"/api/v1/batch-analyses/{payload['batch_analysis_id']}/results?limit=1&offset=1", headers=headers)
    assert results.status_code == 200
    assert results.json()["total"] == 4
    assert results.json()["items"][0]["row_number"] == 3
    assert results.json()["items"][0]["row_state"] == "rejected"
    assert results.json()["items"][0]["validation_errors"][0]["field"] == "rating"
    assert results.json()["items"][0]["prediction"] is None

    with client._testing_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Reviewer)) == 1
        assert session.scalar(select(func.count()).select_from(Product)) == 1
        assert session.scalar(select(func.count()).select_from(Review)) == 2
        assert session.scalar(select(func.count()).select_from(BatchAnalysisRow)) == 4
        assert session.scalar(select(func.count()).select_from(InferenceRun)) == 0
        stored_batch = session.get(BatchAnalysis, payload["batch_analysis_id"])
        assert stored_batch.upload_sha256 == payload["upload_sha256"]


def test_batch_csv_global_validation_and_duplicate_database_key(client, reader_token):
    headers = {"Authorization": f"Bearer {reader_token}"}
    missing_header = client.post(
        "/api/v1/batch-analyses", headers=headers,
        data={"source_system": "batch-test"},
        files={"file": ("bad.csv", b"review_id,rating\nr-1,5\n", "text/csv")},
    )
    assert missing_header.status_code == 422
    assert missing_header.json()["error"]["code"] == "missing_csv_columns"

    csv_content = (
        "review_id,reviewer_id,product_id,rating,review_date,review_text\n"
        "db-existing,u-1,p-1,5,2025-01-01,First\n"
        "db-existing,u-1,p-1,5,2025-01-01,Duplicate database key\n"
    ).encode()
    uploaded = client.post(
        "/api/v1/batch-analyses", headers=headers,
        data={"source_system": "batch-test"},
        files={"file": ("duplicates.csv", csv_content, "text/csv")},
    )
    assert uploaded.status_code == 201
    assert uploaded.json()["accepted_count"] == 1
    duplicate = client.post(
        "/api/v1/batch-analyses", headers=headers,
        data={"source_system": "batch-test"},
        files={"file": ("duplicate-existing.csv", csv_content.split(b"\n", 1)[0] + b"\n" + csv_content.split(b"\n", 1)[1], "text/csv")},
    )
    assert duplicate.status_code == 201
    result = client.get(f"/api/v1/batch-analyses/{duplicate.json()['batch_analysis_id']}/results", headers=headers)
    assert result.json()["items"][0]["row_state"] == "rejected"
    assert result.json()["items"][0]["validation_errors"][0]["code"] == "already_imported"


def test_batch_history_requires_explicit_admin_permission(client, reader_token, admin_token):
    with client._testing_session_factory() as session:
        snapshot = GraphSnapshot(snapshot_key="batch-permission-snapshot", dataset_name="test",
                                 dataset_sha256="e" * 64, artifact_uri="test://graph",
                                 artifact_sha256="f" * 64, graph_builder_version="test-v1",
                                 relation_schema_version="test-v1", split_protocol_key="test-split",
                                 node_count=1, storage_status="available")
        session.add(snapshot)
        session.commit()
        snapshot_id = snapshot.graph_snapshot_id

    csv_content = (
        "review_id,reviewer_id,product_id,rating,review_date,review_text\n"
        "r-1,u-1,p-1,5,2025-01-01,Review text\n"
    ).encode()
    upload = lambda: client.post(
        "/api/v1/batch-analyses",
        headers={"Authorization": f"Bearer {reader_token}"},
        data={"source_system": "permission-test", "historic_graph_snapshot_id": str(snapshot_id)},
        files={"file": ("reviews.csv", csv_content, "text/csv")},
    )
    refused = upload()
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "snapshot_not_permitted"

    permission = client.patch(
        f"/api/v1/graph-snapshots/{snapshot_id}/batch-context-permission",
        headers={"Authorization": f"Bearer {admin_token}"}, json={"permitted": True},
    )
    assert permission.status_code == 200
    assert permission.json()["batch_context_permitted"] is True
    accepted = upload()
    assert accepted.status_code == 201
    assert accepted.json()["historic_graph_snapshot_id"] == snapshot_id
    assert "historic_graph_snapshot_not_selected" not in accepted.json()["blocking_reasons"]
