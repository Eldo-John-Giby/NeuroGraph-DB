"""Project a scored upload's actual inference edges into a batch-scoped Neo4j graph."""
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BatchAnalysis, BatchAnalysisRow, FraudPrediction, InductivePredictionEvidence, Review
from app.services.batch_csv import BatchReviewInput
from app.services.batch_graph import load_permitted_historic_context
from app.services.inductive_relations import node_order, stitch_arrivals
from app.services.neo4j_synthetic_projection import _new_driver
from app.security import as_utc


def project_and_read_batch_graph(db: Session, batch: BatchAnalysis) -> dict:
    if batch.status != 'completed' or not batch.inference_run_id:
        raise ValueError('Only a completed analysis has a model-used relationship graph')
    records = db.execute(select(
        Review.review_id, Review.reviewer_id, Review.product_id, Review.rating,
        Review.reviewed_at, Review.review_text, Review.source_review_key,
    ).join(BatchAnalysisRow, BatchAnalysisRow.review_id == Review.review_id).where(
        BatchAnalysisRow.batch_analysis_id == batch.batch_analysis_id,
        BatchAnalysisRow.row_state == 'accepted',
    )).all()
    arrivals = sorted([BatchReviewInput(r.review_id, r.reviewer_id, r.product_id, r.rating,
                                        as_utc(r.reviewed_at), r.review_text, r.source_review_key) for r in records], key=node_order)
    context = load_permitted_historic_context(db, batch.historic_graph_snapshot_id, split='train')
    cutoff = min(r.reviewed_at for r in arrivals)
    history = sorted([r for r in context.reviews if r.reviewed_at <= cutoff], key=node_order)
    pairs, _ = stitch_arrivals(history, arrivals)
    hash_data = {name: [a for a, b in pairs[name]] + [b for a, b in pairs[name]] for name in pairs}
    hash_data.update(n_hist=len(history), n_up=len(arrivals))
    graph_sha = hashlib.sha256(json.dumps(hash_data, sort_keys=True).encode()).hexdigest()
    predictions = db.execute(select(FraudPrediction, InductivePredictionEvidence).join(
        InductivePredictionEvidence, InductivePredictionEvidence.fraud_prediction_id == FraudPrediction.fraud_prediction_id,
    ).where(FraudPrediction.inference_run_id == batch.inference_run_id)).all()
    if len(predictions) != len(arrivals) or any(e.stitched_graph_sha256 != graph_sha for _, e in predictions):
        raise ValueError('Stored predictions do not match this reconstructed inference graph; no graph was projected')
    score_by_id = {p.review_id: (float(p.risk_score), p.predicted_label) for p, _ in predictions}
    nodes = [*history, *arrivals]
    included = set(range(len(history), len(nodes)))
    for relation in pairs.values():
        for source, target in relation:
            included.update((source, target))
    batch_id = batch.batch_analysis_id
    key = lambda index: f'upload-analysis:{batch_id}:review:{nodes[index].review_id}'
    node_values = [{'key': key(index), 'batch_id': batch_id, 'review_id': nodes[index].review_id,
                    'review_key': nodes[index].source_review_key or str(nodes[index].review_id),
                    'reviewer_id': nodes[index].reviewer_id, 'product_id': nodes[index].product_id,
                    'rating': nodes[index].rating, 'reviewed_at': nodes[index].reviewed_at.isoformat(),
                    'historical': index < len(history),
                    'risk_score': score_by_id.get(nodes[index].review_id, (None, None))[0],
                    'predicted_label': score_by_id.get(nodes[index].review_id, (None, None))[1],
                    'graph_sha256': graph_sha} for index in sorted(included)]
    links = [{'source': key(source), 'target': key(target), 'relation': relation.upper(),
              'key': f'{batch_id}:{relation}:{source}:{target}', 'batch_id': batch_id}
             for relation, values in pairs.items() for source, target in values]

    def write(tx):
        tx.run('UNWIND $nodes AS row MERGE (n:UploadAnalysisReview {key: row.key}) SET n += row', nodes=node_values).consume()
        tx.run('UNWIND $links AS row MATCH (a:UploadAnalysisReview {key: row.source}) '
               'MATCH (b:UploadAnalysisReview {key: row.target}) '
               'MERGE (a)-[r:CONTEXT_FOR {key: row.key}]->(b) SET r += row', links=links).consume()

    driver = _new_driver()
    try:
        with driver.session() as session:
            session.execute_write(write)
            stored_nodes = session.execute_read(lambda tx: [dict(row['properties']) for row in tx.run(
                'MATCH (n:UploadAnalysisReview {batch_id: $batch_id}) RETURN properties(n) AS properties ORDER BY n.reviewed_at, n.key', batch_id=batch_id)])
            stored_links = session.execute_read(lambda tx: [dict(row['properties']) for row in tx.run(
                'MATCH (:UploadAnalysisReview {batch_id: $batch_id})-[r:CONTEXT_FOR {batch_id: $batch_id}]->(:UploadAnalysisReview {batch_id: $batch_id}) '
                'RETURN properties(r) AS properties ORDER BY r.key', batch_id=batch_id)])
        return {'batch_analysis_id': batch_id, 'source': 'neo4j_upload_analysis', 'model_inference_used': True,
                'graph_sha256': graph_sha, 'nodes': stored_nodes, 'relationships': stored_links}
    finally:
        driver.close()
