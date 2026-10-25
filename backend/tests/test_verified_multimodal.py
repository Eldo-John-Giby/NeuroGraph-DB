"""Tests for the verified raw YelpChi multimodal GNN endpoints and runtime."""

from fastapi.testclient import TestClient


def test_verified_multimodal_status(client: TestClient, reader_token: str):
    headers = {"Authorization": f"Bearer {reader_token}"}
    response = client.get("/api/v1/verified-multimodal/status", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["available"] is True
    assert data["runtime_loaded"] is True
    assert data["scores_cached"] is True
    assert data["run_id"] == "raw_yelpchi_multimodal_seed42_20261025T071547Z"
    assert data["manifest_sha256"] == "653729f3fdd63f23ce82849b37dfa76a4dd08242bb5c05761a44ca799692defb"
    assert abs(data["threshold"] - 0.6732323232323232) < 1e-6
    assert data["node_count"] == 47176
    assert abs(data["metrics"]["roc_auc"] - 0.8438816) < 1e-4
    assert abs(data["metrics"]["f1_macro"] - 0.6859931) < 1e-4

    fixed = data["fixed_review"]
    assert fixed["review_id"] == "--AweNX8vPGD"
    assert fixed["node_index"] == 2
    assert fixed["reproduced"] is True
    assert abs(fixed["observed_fraud_score"] - fixed["expected_fraud_score"]) <= fixed["tolerance"]


def test_verified_multimodal_predict_known_node(client: TestClient, reader_token: str):
    headers = {"Authorization": f"Bearer {reader_token}"}
    response = client.post(
        "/api/v1/verified-multimodal/predict",
        headers=headers,
        json={"review_ids": ["--AweNX8vPGD"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == "raw_yelpchi_multimodal_seed42_20261025T071547Z"
    assert data["mode"] == "transductive_known_node"
    assert len(data["predictions"]) == 1

    pred = data["predictions"][0]
    assert pred["review_id"] == "--AweNX8vPGD"
    assert pred["node_index"] == 2
    assert abs(pred["fraud_score"] - 0.00680473) < 1e-5
    assert pred["predicted_label"] == 0


def test_verified_multimodal_predict_unknown_node_rejected(client: TestClient, reader_token: str):
    headers = {"Authorization": f"Bearer {reader_token}"}
    response = client.post(
        "/api/v1/verified-multimodal/predict",
        headers=headers,
        json={"review_ids": ["unknown-nonexistent-review-id"]},
    )
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "unknown_graph_node"
    assert "not part of verified graph snapshot" in data["error"]["message"]
    assert "unknown-nonexistent-review-id" in str(data["error"]["details"]) or "unknown-nonexistent-review-id" in data["error"]["message"]


def test_verified_multimodal_results_pagination(client: TestClient, reader_token: str):
    headers = {"Authorization": f"Bearer {reader_token}"}
    response = client.get("/api/v1/verified-multimodal/results?limit=5&offset=0", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 47176
    assert data["limit"] == 5
    assert data["offset"] == 0
    assert len(data["items"]) == 5

    # Check sorted descending by fraud score
    scores = [item["fraud_score"] for item in data["items"]]
    assert scores == sorted(scores, reverse=True)
    # Top score should be above 0.95
    assert scores[0] > 0.95


def test_verified_multimodal_results_invalid_pagination(client: TestClient, reader_token: str):
    headers = {"Authorization": f"Bearer {reader_token}"}
    response = client.get("/api/v1/verified-multimodal/results?limit=0&offset=0", headers=headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_pagination"

    response = client.get("/api/v1/verified-multimodal/results?limit=101&offset=0", headers=headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_pagination"
