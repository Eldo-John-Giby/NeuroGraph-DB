#!/usr/bin/env python3
"""Register the verified raw YelpChi inductive benchmark run in PostgreSQL.

Registers PreprocessingVersion, GraphSnapshot, and ModelVersion with full provenance,
manifest SHA, validation threshold (0.787071), and evaluation metrics.
Idempotent: safe to run multiple times.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "backend"))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import make_engine
from app.models import GraphSnapshot, ModelVersion, PreprocessingVersion

BUNDLE_DIR = REPO_ROOT / "artifacts/verified_inductive/raw_yelpchi_inductive_seed42_20261025T125837Z"
RUN_RECORD_PATH = REPO_ROOT / "docs/runs/raw_yelpchi_inductive_seed42_20261025T125837Z.json"


def register(engine=None) -> dict[str, int]:
    if engine is None:
        engine = make_engine()

    manifest_path = BUNDLE_DIR / "run_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing bundle manifest at {manifest_path}")

    manifest = json.loads(manifest_path.read_text())
    run_record = json.loads(RUN_RECORD_PATH.read_text())
    prep_config = json.loads((BUNDLE_DIR / "preprocessing.json").read_text())
    model_config = json.loads((BUNDLE_DIR / "model_config.json").read_text())
    metrics_data = json.loads((BUNDLE_DIR / "metrics.json").read_text())

    now = datetime.now(timezone.utc)
    results = {}

    with Session(engine) as session:
        # 1. PreprocessingVersion
        prep_key = "raw-yelpchi-inductive-roberta-v1"
        prep_sha = manifest["files"]["preprocessing.json"]
        prep = session.scalar(select(PreprocessingVersion).where(PreprocessingVersion.version_key == prep_key))
        if prep is None:
            prep = PreprocessingVersion(
                version_key=prep_key,
                preprocessing_sha256=prep_sha,
                preprocessing_config=prep_config,
                code_revision=model_config["tokenizer"].get("resolved_revision", "e2da8e2f811d1448a5b465c236feacd80ffbac7b"),
                lifecycle_status="verified",
                verified_at=now,
            )
            session.add(prep)
            session.flush()
            print(f"Created PreprocessingVersion: id={prep.preprocessing_version_id}, key={prep_key}")
        else:
            print(f"Existing PreprocessingVersion: id={prep.preprocessing_version_id}, key={prep_key}")
        results["preprocessing_version_id"] = prep.preprocessing_version_id

        # 2. GraphSnapshot
        snapshot_key = "raw-yelpchi-inductive-graph-47k-v1"
        graph_artifact_sha = manifest["files"]["serving_graph.pt"]
        dataset_sha = "dbd3769b608bf249ed484f87d291e5d73f4988fd33e26f1bb96a50e8cdd418c8"
        edge_counts = {"rur": 54338, "rsr": 1658662, "rtr": 450271}

        snapshot = session.scalar(select(GraphSnapshot).where(GraphSnapshot.snapshot_key == snapshot_key))
        if snapshot is None:
            snapshot = GraphSnapshot(
                snapshot_key=snapshot_key,
                dataset_name="samygithub/collective-opinion-spam-detection",
                dataset_sha256=dataset_sha,
                artifact_uri="artifacts/verified_inductive/raw_yelpchi_inductive_seed42_20261025T125837Z/serving_graph.pt",
                artifact_sha256=graph_artifact_sha,
                graph_builder_version="build_yelpchi_inductive_graph.py@ab41cde",
                relation_schema_version="inductive-rur-rsr-rtr-v1",
                split_protocol_key="chronological_arrival_windows_60_20_20",
                node_count=int(model_config.get("node_count", 47176)),
                edge_counts=edge_counts,
                storage_status="available",
                batch_context_permitted=True,
                context_scope_key="inductive-rur-rsr-rtr-v1",
                provenance="real",
            )
            session.add(snapshot)
            session.flush()
            print(f"Created GraphSnapshot: id={snapshot.graph_snapshot_id}, key={snapshot_key}")
        else:
            print(f"Existing GraphSnapshot: id={snapshot.graph_snapshot_id}, key={snapshot_key}")
        results["graph_snapshot_id"] = snapshot.graph_snapshot_id

        # 3. ModelVersion
        model_key = "raw-yelpchi-inductive-roberta-gnn-v1"
        model_config_sha = manifest["files"]["model_config.json"]
        checkpoint_sha = manifest["files"]["model_state.pt"]
        threshold = Decimal(str(round(float(manifest["threshold"]), 7)))

        model = session.scalar(select(ModelVersion).where(ModelVersion.version_key == model_key))
        if model is None:
            model = ModelVersion(
                version_key=model_key,
                model_name="raw_yelpchi_inductive_roberta_gnn_v1",
                architecture_version="inductive_roberta_relation_specific_pyg_graphsage_cross_attention",
                architecture_config={
                    "text_dim": model_config["text_dim"],
                    "meta_dim": model_config["meta_dim"],
                    "hidden_dim": model_config["hidden_dim"],
                    "dropout": model_config["dropout"],
                    "relations": model_config["relations"],
                    "relation_policy": model_config.get("relation_policy", "inductive-rur-rsr-rtr-v1"),
                    "run_id": manifest["run_id"],
                    "manifest_sha256": run_record["bundle_manifest_sha256"],
                    "evaluation_protocol": "inductive_temporal_replay",
                    "metrics": metrics_data,
                },
                config_sha256=model_config_sha,
                checkpoint_uri="artifacts/verified_inductive/raw_yelpchi_inductive_seed42_20261025T125837Z/model_state.pt",
                checkpoint_sha256=checkpoint_sha,
                preprocessing_version_id=prep.preprocessing_version_id,
                input_contract_version="raw_yelpchi_inductive_input_v1",
                supported_inference_mode="inductive_batch_v1",
                recommended_threshold=threshold,
                threshold_source=f"validation_f1_macro (F1={metrics_data['test']['f1_macro']:.4f}, ROC-AUC={metrics_data['test']['roc_auc']:.4f})",
                lifecycle_status="verified",
                provenance="real",
                verification_at=now,
            )
            session.add(model)
            session.flush()
            print(f"Created ModelVersion: id={model.model_version_id}, key={model_key}")
        else:
            print(f"Existing ModelVersion: id={model.model_version_id}, key={model_key}")
        results["model_version_id"] = model.model_version_id

        session.commit()

    return results


if __name__ == "__main__":
    res = register()
    print("Registration completed successfully:", res)
