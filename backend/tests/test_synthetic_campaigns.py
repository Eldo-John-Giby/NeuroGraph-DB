from datetime import datetime, timezone

from app.models import (Product, Review, Reviewer, SyntheticCampaign,
                        SyntheticCampaignMember, SyntheticCampaignReview)


def _at(day: int, hour: int = 12):
    return datetime(2025, 4, day, hour, tzinfo=timezone.utc)


def _scenario(db):
    target = Product(source_system="synthetic_demo", external_product_key="restaurant-target-test",
                     display_name="Test Harbor · synthetic restaurant")
    prior_product = Product(source_system="synthetic_demo", external_product_key="restaurant-prior-test",
                            display_name="Test Cedar · synthetic restaurant")
    account_a = Reviewer(source_system="synthetic_demo", external_reviewer_key="test-account-a")
    account_b = Reviewer(source_system="synthetic_demo", external_reviewer_key="test-account-b")
    db.add_all([target, prior_product, account_a, account_b]); db.flush()
    prior = SyntheticCampaign(
        campaign_key="test-prior-campaign", campaign_name="Prior test burst", product_id=prior_product.product_id,
        prior_start_at=_at(1), prior_end_at=_at(2), attack_start_at=_at(3), attack_end_at=_at(3, 20),
        description="Synthetic prior campaign", provenance="synthetic_demo")
    db.add(prior); db.flush()
    campaign = SyntheticCampaign(
        campaign_key="test-restaurant-attack", campaign_name="Test restaurant attack", product_id=target.product_id,
        prior_campaign_id=prior.synthetic_campaign_id, prior_start_at=_at(4), prior_end_at=_at(8),
        attack_start_at=_at(10), attack_end_at=_at(11), description="Synthetic review-bombing test",
        provenance="synthetic_demo")
    db.add(campaign); db.flush()
    old_review = Review(source_system="synthetic_demo", source_review_key="prior-test-review",
                       reviewer_id=account_a.reviewer_id, product_id=prior_product.product_id,
                       rating=1, reviewed_at=_at(3, 14), review_text="Prior burst text")
    db.add(old_review); db.flush()
    db.add_all([
        SyntheticCampaignReview(synthetic_campaign_id=prior.synthetic_campaign_id, review_id=old_review.review_id,
                                campaign_period="attack", evidence_note="Prior burst evidence", provenance="synthetic_demo"),
        SyntheticCampaignMember(synthetic_campaign_id=prior.synthetic_campaign_id, reviewer_id=account_a.reviewer_id,
                                membership_type="prior_participant", provenance="synthetic_demo"),
    ])
    baseline = [
        Review(source_system="synthetic_demo", source_review_key="baseline-a", reviewer_id=account_b.reviewer_id,
               product_id=target.product_id, rating=4, reviewed_at=_at(5), review_text="Good service and meal."),
        Review(source_system="synthetic_demo", source_review_key="baseline-b", reviewer_id=account_b.reviewer_id,
               product_id=target.product_id, rating=5, reviewed_at=_at(7), review_text="Pleasant visit."),
    ]
    attack = [
        Review(source_system="synthetic_demo", source_review_key="attack-a", reviewer_id=account_a.reviewer_id,
               product_id=target.product_id, rating=1, reviewed_at=_at(10), review_text="Cold food and slow service."),
        Review(source_system="synthetic_demo", source_review_key="attack-b", reviewer_id=account_a.reviewer_id,
               product_id=target.product_id, rating=2, reviewed_at=_at(10, 13), review_text="Cold food, slow service."),
    ]
    organic_attack_window = Review(source_system="synthetic_demo", source_review_key="organic-attack-window",
                                  reviewer_id=account_b.reviewer_id, product_id=target.product_id,
                                  rating=4, reviewed_at=_at(10, 15), review_text="A separate synthetic review.")
    db.add_all(baseline + attack + [organic_attack_window]); db.flush()
    for review in baseline:
        db.add(SyntheticCampaignReview(synthetic_campaign_id=campaign.synthetic_campaign_id,
                                       review_id=review.review_id, campaign_period="prior",
                                       evidence_note="Comparison-window observation", provenance="synthetic_demo"))
    for review in attack:
        db.add(SyntheticCampaignReview(synthetic_campaign_id=campaign.synthetic_campaign_id,
                                       review_id=review.review_id, campaign_period="attack",
                                       evidence_note="Synthetic campaign attack-window evidence", provenance="synthetic_demo"))
    db.add(SyntheticCampaignMember(synthetic_campaign_id=campaign.synthetic_campaign_id,
                                   reviewer_id=account_a.reviewer_id, membership_type="attack_participant",
                                   provenance="synthetic_demo"))
    db.flush()


def test_synthetic_campaign_analytics_endpoints(client, reader_token):
    with client._testing_session_factory() as db:
        _scenario(db)
        target = db.query(Product).filter_by(external_product_key="restaurant-target-test").one()
        non_synthetic_author = Reviewer(source_system="other_source", external_reviewer_key="other-account")
        db.add(non_synthetic_author); db.flush()
        db.add(Review(source_system="other_source", source_review_key="out-of-scope-review",
                      reviewer_id=non_synthetic_author.reviewer_id, product_id=target.product_id,
                      rating=1, reviewed_at=_at(10, 16), review_text="Must not enter synthetic aggregates."))
        db.commit()
    headers = {"Authorization": f"Bearer {reader_token}"}
    base = "/api/v1/synthetic-campaigns/test-restaurant-attack"

    summary = client.get(f"{base}/summary", headers=headers)
    assert summary.status_code == 200
    body = summary.json()
    assert body["provenance"] == "synthetic_demo"
    assert body["attack_review_count"] == 2
    assert body["one_star_review_count"] == 1
    assert body["distinct_attack_reviewers"] == 1
    assert body["reviewers_overlapping_prior_campaign"] == 1
    assert "fraud_score" not in body

    timeline_response = client.get(f"{base}/rating-over-time", headers=headers)
    assert timeline_response.status_code == 200, timeline_response.text
    timeline = timeline_response.json()
    assert timeline["provenance"] == "synthetic_demo"
    assert any(abs(row["observed_mean_rating"] - 7 / 3) < 1e-9 for row in timeline["items"])

    comparison = client.get(f"{base}/rating-comparison", headers=headers).json()
    assert comparison["observed_attack_window"]["review_count"] == 3
    assert comparison["observed_attack_window"]["mean_rating"] == 7 / 3
    assert comparison["scenario_adjusted_attack_window"]["review_count"] == 1
    assert comparison["scenario_adjusted_attack_window"]["mean_rating"] == 4.0
    assert "not a model risk adjustment" in comparison["formula"]

    volume = client.get(f"{base}/volume-by-day", headers=headers).json()
    assert volume["comparison_review_count"] == 2
    assert volume["attack_review_count"] == 3
    assert volume["attack_to_comparison_daily_volume_ratio"] > 1

    members = client.get(f"{base}/members?limit=1&offset=0", headers=headers).json()
    assert members["total"] == 1
    evidence = members["items"][0]["evidence"]
    assert evidence["overlapped_prior_campaign"] is True
    assert evidence["attack_review_keys"] == ["attack-a", "attack-b"]
    assert "no model score or attention used" in evidence["source"]


def test_synthetic_campaign_endpoints_are_authenticated_and_synthetic_scoped(client, reader_token):
    assert client.get("/api/v1/synthetic-campaigns/missing/summary").status_code == 401
    with client._testing_session_factory() as db:
        product = Product(source_system="real_source", external_product_key="real-product", display_name="Real")
        db.add(product); db.flush()
        campaign = SyntheticCampaign(campaign_key="bad-provenance", campaign_name="Bad", product_id=product.product_id,
                                     prior_start_at=_at(1), prior_end_at=_at(2), attack_start_at=_at(3),
                                     attack_end_at=_at(4), description="bad", provenance="real")
        db.add(campaign)
        import pytest
        from sqlalchemy.exc import IntegrityError
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    response = client.get("/api/v1/synthetic-campaigns/missing/summary",
                          headers={"Authorization": f"Bearer {reader_token}"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "synthetic_campaign_not_found"


def test_neo4j_projection_payload_uses_only_linked_synthetic_records(client):
    from app.services.neo4j_synthetic_projection import (build_projection_payload,
                                                         project_synthetic_campaign)

    with client._testing_session_factory() as db:
        _scenario(db)
        payload = build_projection_payload(db, "test-restaurant-attack")
        assert payload["provenance"] == "synthetic_demo"
        assert set(payload["nodes"]) == {"Restaurant", "Reviewer", "Review", "Campaign"}
        assert len(payload["nodes"]["Campaign"]) == 2
        assert len(payload["nodes"]["Restaurant"]) == 2
        assert all(node["provenance"] == "synthetic_demo"
                   for label_nodes in payload["nodes"].values() for node in label_nodes.values())
        assert payload["relationships"]["OVERLAPS_WITH"][0]["overlap_count"] == 1
        assert len(payload["relationships"]["HAS_REVIEW"]) == 5
        assert not any("score" in str(node).lower() or "attention" in str(node).lower()
                       for label_nodes in payload["nodes"].values() for node in label_nodes.values())

        class Result:
            def consume(self):
                return None

        class FakeTransaction:
            def __init__(self):
                self.queries = []

            def run(self, query, **parameters):
                self.queries.append((query, parameters))
                return Result()

        class FakeSession:
            def __init__(self):
                self.tx = FakeTransaction()
                self.constraints = []

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def run(self, query):
                self.constraints.append(query)
                return Result()

            def execute_write(self, callback, arg):
                callback(self.tx, arg)

        class FakeDriver:
            def __init__(self):
                self.session_value = FakeSession()

            def session(self):
                return self.session_value

            def close(self):
                pass

        fake = FakeDriver()
        first = project_synthetic_campaign(db, "test-restaurant-attack", driver=fake)
        second = project_synthetic_campaign(db, "test-restaurant-attack", driver=fake)
        assert first["node_counts"] == second["node_counts"]
        assert all("MERGE" in query for query, _ in fake.session_value.tx.queries)


def test_campaign_graph_endpoint_reports_neo4j_unavailable_and_reads_only(client, reader_token, monkeypatch):
    from app.api import campaigns as campaign_api
    from app.services.neo4j_synthetic_projection import Neo4jProjectionUnavailable

    with client._testing_session_factory() as db:
        _scenario(db)
        db.commit()

    def unavailable(_campaign_key):
        raise Neo4jProjectionUnavailable("Neo4j is not configured.")

    monkeypatch.setattr(campaign_api, "read_synthetic_campaign_graph", unavailable)
    headers = {"Authorization": f"Bearer {reader_token}"}
    path = "/api/v1/synthetic-campaigns/test-restaurant-attack/graph"
    unavailable_response = client.get(path, headers=headers)
    assert unavailable_response.status_code == 503
    assert unavailable_response.json()["error"]["code"] == "neo4j_unavailable"
    assert unavailable_response.json()["error"]["provenance"] == "synthetic_demo"

    monkeypatch.setattr(campaign_api, "read_synthetic_campaign_graph", lambda key: {
        "campaign_key": key, "provenance": "synthetic_demo", "model_inference_used": False,
        "nodes": [{"labels": ["Campaign"], "key": "synthetic_demo:campaign:test-restaurant-attack",
                   "campaign_key": key}],
        "relationships": [],
    })
    graph_response = client.get(path, headers=headers)
    assert graph_response.status_code == 200
    assert graph_response.json()["provenance"] == "synthetic_demo"
    assert graph_response.json()["model_inference_used"] is False
