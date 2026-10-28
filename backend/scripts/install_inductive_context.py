#!/usr/bin/env python3
"""Install the verified YelpChi training-history partition without importing labels.

Checks the committed bundle manifest, its graph-manifest binding, the source CSV
hash, and the complete chronological raw-ID order before writing any history.
Existing snapshots and saved uploads are preserved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import torch
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from app.db import make_engine
from app.models import GraphSnapshotReview, Product, Review, Reviewer
from register_verified_inductive import BUNDLE_DIR, RUN_RECORD_PATH, register

SOURCE = 'yelpchi-inductive-source-v1'


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--training-csv', type=Path, required=True)
    args = parser.parse_args()
    record = json.loads(RUN_RECORD_PATH.read_text())
    manifest_path = BUNDLE_DIR / 'run_manifest.json'
    if sha(manifest_path) != record['bundle_manifest_sha256']:
        raise ValueError('Bundle manifest differs from committed run record')
    manifest = json.loads(manifest_path.read_text())
    for name, expected in manifest['files'].items():
        if sha(BUNDLE_DIR / name) != expected:
            raise ValueError(f'Bundle checksum failed: {name}')
    config = json.loads((BUNDLE_DIR / 'model_config.json').read_text())
    graph_manifest_path = BUNDLE_DIR / 'inductive_graph_manifest.json'
    if sha(graph_manifest_path) != config['graph_manifest_sha256']:
        raise ValueError('Raw graph manifest binding failed')
    graph_manifest = json.loads(graph_manifest_path.read_text())
    if sha(args.training_csv) != graph_manifest['files']['training_csv_sha256']:
        raise ValueError('Raw CSV hash does not match the trained graph')

    # Deliberately exclude Label, including from the selected CSV columns.
    columns = {'review ID': 'key', 'reviewer ID': 'reviewer', 'product ID': 'product',
               'rating_OhNo': 'rating', 'Date': 'date', 'reviews': 'text'}
    rows = pd.read_csv(args.training_csv, usecols=list(columns), dtype=str, keep_default_na=False).rename(columns=columns)
    rows['date'] = pd.to_datetime(rows['date'], utc=True, errors='raise')
    rows = rows.sort_values(['date', 'key'], kind='stable').reset_index(drop=True)
    graph = torch.load(BUNDLE_DIR / 'serving_graph.pt', map_location='cpu', weights_only=True)
    if rows.key.tolist() != graph['review_ids']:
        raise ValueError('CSV review identity/order differs from verified serving graph')
    train = rows.iloc[:int(config['split']['train_nodes'])]
    engine = make_engine()
    ids = register(engine)
    with Session(engine) as db, db.begin():
        reviewer_map = dict(db.execute(select(Reviewer.external_reviewer_key, Reviewer.reviewer_id).where(Reviewer.source_system == SOURCE)).all())
        product_map = dict(db.execute(select(Product.external_product_key, Product.product_id).where(Product.source_system == SOURCE)).all())
        new_reviewers = [{'source_system': SOURCE, 'external_reviewer_key': key} for key in sorted(set(train.reviewer) - reviewer_map.keys())]
        new_products = [{'source_system': SOURCE, 'external_product_key': key} for key in sorted(set(train['product']) - product_map.keys())]
        if new_reviewers: db.execute(insert(Reviewer), new_reviewers)
        if new_products: db.execute(insert(Product), new_products)
        reviewer_map = dict(db.execute(select(Reviewer.external_reviewer_key, Reviewer.reviewer_id).where(Reviewer.source_system == SOURCE)).all())
        product_map = dict(db.execute(select(Product.external_product_key, Product.product_id).where(Product.source_system == SOURCE)).all())
        review_map = dict(db.execute(select(Review.source_review_key, Review.review_id).where(Review.source_system == SOURCE)).all())
        fresh = [{'source_system': SOURCE, 'source_review_key': row.key,
                  'reviewer_id': reviewer_map[row.reviewer], 'product_id': product_map[row.product],
                  'rating': int(float(row.rating)), 'reviewed_at': row.date.to_pydatetime(), 'review_text': row.text}
                 for row in train.itertuples(index=False) if row.key not in review_map]
        if fresh: db.execute(insert(Review), fresh)
        review_map = dict(db.execute(select(Review.source_review_key, Review.review_id).where(Review.source_system == SOURCE)).all())
        members = set(db.scalars(select(GraphSnapshotReview.review_id).where(GraphSnapshotReview.graph_snapshot_id == ids['graph_snapshot_id'])))
        fresh_members = [{'graph_snapshot_id': ids['graph_snapshot_id'], 'review_id': review_map[key], 'split': 'train'}
                         for key in train.key if review_map[key] not in members]
        if fresh_members: db.execute(insert(GraphSnapshotReview), fresh_members)
    print(json.dumps({'status': 'installed', 'snapshot_id': ids['graph_snapshot_id'],
                      'historical_training_reviews': len(train), 'labels_imported': False}, indent=2))


if __name__ == '__main__':
    main()
