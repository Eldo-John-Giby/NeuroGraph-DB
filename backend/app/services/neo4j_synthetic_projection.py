"""Idempotent, provenance-scoped PostgreSQL to Neo4j campaign projection."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (Product, Review, Reviewer, SyntheticCampaign,
                        SyntheticCampaignMember, SyntheticCampaignReview)

SYNTHETIC = "synthetic_demo"


class Neo4jProjectionUnavailable(RuntimeError):
    """Neo4j is not configured, unreachable, or does not support the query API."""


class ProjectionSourceInvalid(RuntimeError):
    """The PostgreSQL campaign references data outside the synthetic lane."""


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def build_projection_payload(db: Session, campaign_key: str) -> dict[str, Any]:
    """Read the campaign and linked prior campaign from approved synthetic rows."""
    main = db.scalar(select(SyntheticCampaign).where(
        SyntheticCampaign.campaign_key == campaign_key,
        SyntheticCampaign.provenance == SYNTHETIC,
    ))
    if main is None:
        raise LookupError("Synthetic campaign was not found.")
    campaigns = [main]
    if main.prior_campaign_id:
        previous = db.get(SyntheticCampaign, main.prior_campaign_id)
        if previous is None or previous.provenance != SYNTHETIC:
            raise ProjectionSourceInvalid("Linked prior campaign is not synthetic_demo.")
        campaigns.append(previous)
    campaign_ids = [row.synthetic_campaign_id for row in campaigns]
    campaign_keys = [row.campaign_key for row in campaigns]

    products_by_id = {row.product_id: row for row in db.scalars(select(Product).where(
        Product.product_id.in_([row.product_id for row in campaigns]),
        Product.source_system == SYNTHETIC,
    ))}
    if len(products_by_id) != len(campaigns):
        raise ProjectionSourceInvalid("A campaign restaurant is missing or outside synthetic_demo.")

    member_rows = db.execute(select(SyntheticCampaignMember, Reviewer).join(
        Reviewer, Reviewer.reviewer_id == SyntheticCampaignMember.reviewer_id
    ).where(SyntheticCampaignMember.synthetic_campaign_id.in_(campaign_ids))).all()
    link_rows = db.execute(select(SyntheticCampaignReview, Review).join(
        Review, Review.review_id == SyntheticCampaignReview.review_id
    ).where(SyntheticCampaignReview.synthetic_campaign_id.in_(campaign_ids))
      .order_by(Review.reviewed_at, Review.review_id)).all()
    if any(member.provenance != SYNTHETIC or reviewer.source_system != SYNTHETIC
           for member, reviewer in member_rows):
        raise ProjectionSourceInvalid("Campaign membership contains non-synthetic provenance or reviewer data.")
    if any(link.provenance != SYNTHETIC or review.source_system != SYNTHETIC
           for link, review in link_rows):
        raise ProjectionSourceInvalid("Campaign evidence contains non-synthetic provenance or review data.")

    reviewers: dict[int, Reviewer] = {reviewer.reviewer_id: reviewer for _, reviewer in member_rows}
    products = dict(products_by_id)
    for _, review in link_rows:
        if review.reviewer_id is None or review.product_id is None:
            raise ProjectionSourceInvalid("Campaign review is missing its synthetic reviewer or restaurant relation.")
        reviewer = db.get(Reviewer, review.reviewer_id)
        product = db.get(Product, review.product_id)
        if reviewer is None or reviewer.source_system != SYNTHETIC:
            raise ProjectionSourceInvalid("Campaign review has a missing or non-synthetic reviewer.")
        if product is None or product.source_system != SYNTHETIC:
            raise ProjectionSourceInvalid("Campaign review has a missing or non-synthetic restaurant.")
        reviewers[reviewer.reviewer_id] = reviewer
        products[product.product_id] = product

    campaign_by_id = {row.synthetic_campaign_id: row for row in campaigns}
    campaign_scope_by_id = {row.synthetic_campaign_id: [main.campaign_key, row.campaign_key]
                            if row.synthetic_campaign_id != main.synthetic_campaign_id else [main.campaign_key]
                            for row in campaigns}
    reviewer_campaign_keys: dict[int, set[str]] = defaultdict(set)
    for member, reviewer in member_rows:
        reviewer_campaign_keys[reviewer.reviewer_id].update(campaign_scope_by_id[member.synthetic_campaign_id])
    review_links_by_id: dict[int, list[tuple[SyntheticCampaignReview, Review]]] = defaultdict(list)
    for link, review in link_rows:
        review_links_by_id[review.review_id].append((link, review))

    nodes: dict[str, dict[str, Any]] = {"Restaurant": {}, "Reviewer": {}, "Review": {}, "Campaign": {}}
    for product in products.values():
        key = f"{SYNTHETIC}:restaurant:{product.product_id}"
        nodes["Restaurant"][key] = {"key": key, "provenance": SYNTHETIC,
            "source_system": product.source_system, "product_id": product.product_id,
            "external_product_key": product.external_product_key, "name": product.display_name,
            "scenario_campaign_keys": campaign_keys}
    for reviewer in reviewers.values():
        key = f"{SYNTHETIC}:reviewer:{reviewer.reviewer_id}"
        scopes = sorted(reviewer_campaign_keys.get(reviewer.reviewer_id, set()) or set(campaign_keys))
        nodes["Reviewer"][key] = {"key": key, "provenance": SYNTHETIC,
            "source_system": reviewer.source_system, "reviewer_id": reviewer.reviewer_id,
            "external_reviewer_key": reviewer.external_reviewer_key,
            "scenario_campaign_keys": scopes}
    for campaign in campaigns:
        key = f"{SYNTHETIC}:campaign:{campaign.campaign_key}"
        nodes["Campaign"][key] = {"key": key, "provenance": SYNTHETIC,
            "campaign_key": campaign.campaign_key, "campaign_name": campaign.campaign_name,
            "description": campaign.description, "product_id": campaign.product_id,
            "prior_start_at": _iso(campaign.prior_start_at), "prior_end_at": _iso(campaign.prior_end_at),
            "attack_start_at": _iso(campaign.attack_start_at), "attack_end_at": _iso(campaign.attack_end_at),
            "scenario_campaign_keys": [main.campaign_key, campaign.campaign_key]
                if campaign.synthetic_campaign_id != main.synthetic_campaign_id else [main.campaign_key]}
    for review_id, linked in review_links_by_id.items():
        review = linked[0][1]
        key = f"{SYNTHETIC}:review:{review.review_id}"
        linked_campaigns = sorted({campaign_by_id[link.synthetic_campaign_id].campaign_key for link, _ in linked})
        scopes = sorted({main.campaign_key, *linked_campaigns})
        nodes["Review"][key] = {"key": key, "provenance": SYNTHETIC,
            "source_system": review.source_system, "review_id": review.review_id,
            "source_review_key": review.source_review_key, "rating": review.rating,
            "reviewed_at": _iso(review.reviewed_at), "review_text": review.review_text,
            "reviewer_id": review.reviewer_id, "product_id": review.product_id,
            "scenario_campaign_keys": scopes}

    relationships: dict[str, list[dict[str, Any]]] = {name: [] for name in
        ("TARGETS", "HAS_REVIEW", "AUTHORED", "ABOUT", "PARTICIPATES_IN", "PREVIOUS_CAMPAIGN", "OVERLAPS_WITH")}
    for campaign in campaigns:
        campaign_node = f"{SYNTHETIC}:campaign:{campaign.campaign_key}"
        restaurant_node = f"{SYNTHETIC}:restaurant:{campaign.product_id}"
        scope = campaign_scope_by_id[campaign.synthetic_campaign_id]
        relationships["TARGETS"].append({"source_key": campaign_node, "target_key": restaurant_node,
            "scenario_campaign_keys": scope, "provenance": SYNTHETIC})
    for link, review in link_rows:
        campaign = campaign_by_id[link.synthetic_campaign_id]
        campaign_node = f"{SYNTHETIC}:campaign:{campaign.campaign_key}"
        review_node = f"{SYNTHETIC}:review:{review.review_id}"
        reviewer_node = f"{SYNTHETIC}:reviewer:{review.reviewer_id}"
        restaurant_node = f"{SYNTHETIC}:restaurant:{review.product_id}"
        scope = sorted({main.campaign_key, campaign.campaign_key})
        relationships["HAS_REVIEW"].append({"source_key": campaign_node, "target_key": review_node,
            "campaign_period": link.campaign_period, "evidence_note": link.evidence_note,
            "scenario_campaign_keys": scope, "provenance": SYNTHETIC})
        relationships["AUTHORED"].append({"source_key": reviewer_node, "target_key": review_node,
            "scenario_campaign_keys": scope, "provenance": SYNTHETIC})
        relationships["ABOUT"].append({"source_key": review_node, "target_key": restaurant_node,
            "scenario_campaign_keys": scope, "provenance": SYNTHETIC})
    for member, reviewer in member_rows:
        campaign = campaign_by_id[member.synthetic_campaign_id]
        relationships["PARTICIPATES_IN"].append({
            "source_key": f"{SYNTHETIC}:reviewer:{reviewer.reviewer_id}",
            "target_key": f"{SYNTHETIC}:campaign:{campaign.campaign_key}",
            "membership_type": member.membership_type,
            "scenario_campaign_keys": campaign_scope_by_id[member.synthetic_campaign_id],
            "provenance": SYNTHETIC,
        })
    if main.prior_campaign_id:
        previous = campaign_by_id[main.prior_campaign_id]
        shared = sorted(set(reviewer_campaign_keys).intersection(
            reviewer.reviewer_id for member, reviewer in member_rows
            if member.synthetic_campaign_id == previous.synthetic_campaign_id
        ).intersection(
            reviewer.reviewer_id for member, reviewer in member_rows
            if member.synthetic_campaign_id == main.synthetic_campaign_id
        ))
        # The two sets are database reviewer IDs; serialize stable external IDs
        # as evidence on the edge rather than exposing any inferred relation.
        shared_keys = sorted(reviewers[reviewer_id].external_reviewer_key for reviewer_id in shared)
        relationships["PREVIOUS_CAMPAIGN"].append({
            "source_key": f"{SYNTHETIC}:campaign:{main.campaign_key}",
            "target_key": f"{SYNTHETIC}:campaign:{previous.campaign_key}",
            "scenario_campaign_keys": [main.campaign_key], "provenance": SYNTHETIC,
        })
        relationships["OVERLAPS_WITH"].append({
            "source_key": f"{SYNTHETIC}:campaign:{main.campaign_key}",
            "target_key": f"{SYNTHETIC}:campaign:{previous.campaign_key}",
            "shared_reviewer_keys": shared_keys, "overlap_count": len(shared_keys),
            "scenario_campaign_keys": [main.campaign_key], "provenance": SYNTHETIC,
        })

    return {"campaign_key": main.campaign_key, "provenance": SYNTHETIC,
            "projection_version": "synthetic-campaign-projection-v1",
            "nodes": nodes, "relationships": relationships}


def _new_driver():
    settings = get_settings()
    if not settings.neo4j_uri:
        raise Neo4jProjectionUnavailable("Neo4j is not configured.")
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise Neo4jProjectionUnavailable("The Neo4j Python driver is not installed.") from exc
    driver = None
    try:
        auth = None
        if settings.neo4j_username or settings.neo4j_password:
            if not settings.neo4j_username or not settings.neo4j_password:
                raise Neo4jProjectionUnavailable("Neo4j credentials are incomplete.")
            auth = (settings.neo4j_username, settings.neo4j_password)
        driver = GraphDatabase.driver(settings.neo4j_uri, auth=auth)
        driver.verify_connectivity()
        return driver
    except Neo4jProjectionUnavailable:
        raise
    except Exception as exc:
        if driver is not None:
            driver.close()
        raise Neo4jProjectionUnavailable("Neo4j is unreachable or rejected the configured connection.") from exc


def _write_projection(tx, payload: dict[str, Any]) -> None:
    # Older projections used the domain ID as a uniqueness key (for example,
    # Review.review_id) and may not have a `key` property yet. Merging only on
    # `key` would then try to create a second Review node and violate that
    # existing uniqueness constraint. Merge on each label's stable domain ID,
    # then write the namespaced key used by current relationship queries.
    identity_properties = {
        "Restaurant": "product_id",
        "Reviewer": "reviewer_id",
        "Review": "review_id",
        "Campaign": "campaign_key",
    }
    for label, rows in payload["nodes"].items():
        identity_property = identity_properties[label]
        query = (f"UNWIND $rows AS row MERGE (n:{label} {{{identity_property}: row.{identity_property}}}) "
                 "WITH n, row, coalesce(n.scenario_campaign_keys, []) + row.scenario_campaign_keys AS scopes "
                 "SET n += row "
                 "SET n.scenario_campaign_keys = reduce(acc = [], scope IN scopes | "
                 "CASE WHEN scope IN acc THEN acc ELSE acc + scope END)")
        tx.run(query, rows=list(rows.values())).consume()
    relation_labels = {
        "TARGETS": ("Campaign", "Restaurant"), "HAS_REVIEW": ("Campaign", "Review"),
        "AUTHORED": ("Reviewer", "Review"), "ABOUT": ("Review", "Restaurant"),
        "PARTICIPATES_IN": ("Reviewer", "Campaign"), "PREVIOUS_CAMPAIGN": ("Campaign", "Campaign"),
        "OVERLAPS_WITH": ("Campaign", "Campaign"),
    }
    for relation, pairs in payload["relationships"].items():
        source_label, target_label = relation_labels[relation]
        query = (f"UNWIND $rows AS row MATCH (a:{source_label} {{key: row.source_key}}) "
                 f"MATCH (b:{target_label} {{key: row.target_key}}) "
                 f"MERGE (a)-[r:{relation}]->(b) "
                 "WITH r, row, coalesce(r.scenario_campaign_keys, []) + row.scenario_campaign_keys AS scopes "
                 "SET r += row "
                 "SET r.scenario_campaign_keys = reduce(acc = [], scope IN scopes | "
                 "CASE WHEN scope IN acc THEN acc ELSE acc + scope END)")
        tx.run(query, rows=pairs).consume()


def project_synthetic_campaign(db: Session, campaign_key: str, *, driver=None) -> dict[str, Any]:
    """Upsert one PostgreSQL campaign projection in a single Neo4j transaction."""
    payload = build_projection_payload(db, campaign_key)
    owns_driver = driver is None
    driver = driver or _new_driver()
    try:
        with driver.session() as session:
            for label in ("Restaurant", "Reviewer", "Review", "Campaign"):
                constraint = f"synthetic_{label.lower()}_key"
                session.run(
                    f"CREATE CONSTRAINT {constraint} IF NOT EXISTS "
                    f"FOR (n:{label}) REQUIRE n.key IS UNIQUE"
                ).consume()
            session.execute_write(_write_projection, payload)
        return {"campaign_key": campaign_key, "provenance": SYNTHETIC,
                "projection_version": payload["projection_version"],
                "node_counts": {label: len(rows) for label, rows in payload["nodes"].items()},
                "relationship_counts": {name: len(rows) for name, rows in payload["relationships"].items()},
                "model_inference_used": False}
    except Exception as exc:
        raise Neo4jProjectionUnavailable("Neo4j projection write failed; PostgreSQL records were not changed.") from exc
    finally:
        if owns_driver:
            driver.close()


def read_synthetic_campaign_graph(campaign_key: str) -> dict[str, Any]:
    """Read an already projected campaign graph; never creates or changes graph data."""
    driver = _new_driver()
    try:
        with driver.session() as session:
            node_result = session.execute_read(lambda tx: list(tx.run(
                "MATCH (n) WHERE n.provenance = $provenance AND $campaign_key IN n.scenario_campaign_keys "
                "RETURN labels(n) AS labels, properties(n) AS properties ORDER BY labels(n)[0], properties(n).key",
                provenance=SYNTHETIC, campaign_key=campaign_key)))
            rel_result = session.execute_read(lambda tx: list(tx.run(
                "MATCH (a)-[r]->(b) WHERE r.provenance = $provenance "
                "AND $campaign_key IN r.scenario_campaign_keys "
                "AND $campaign_key IN a.scenario_campaign_keys AND $campaign_key IN b.scenario_campaign_keys "
                "RETURN type(r) AS type, properties(r) AS properties, a.key AS source_key, b.key AS target_key "
                "ORDER BY type(r), source_key, target_key",
                provenance=SYNTHETIC, campaign_key=campaign_key)))
        nodes = [{"labels": row["labels"], **dict(row["properties"])} for row in node_result]
        relationships = [{"type": row["type"], "source_key": row["source_key"],
                          "target_key": row["target_key"], **dict(row["properties"])} for row in rel_result]
        return {"campaign_key": campaign_key, "provenance": SYNTHETIC,
                "source": "neo4j_synthetic_demo_projection", "model_inference_used": False,
                "nodes": nodes, "relationships": relationships}
    except Exception as exc:
        if isinstance(exc, Neo4jProjectionUnavailable):
            raise
        raise Neo4jProjectionUnavailable("Neo4j graph read failed or the projection is unavailable.") from exc
    finally:
        driver.close()
