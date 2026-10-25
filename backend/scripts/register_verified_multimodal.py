#!/usr/bin/env python3
"""Register the verified raw YelpChi multimodal benchmark run in PostgreSQL.

Registers PreprocessingVersion, GraphSnapshot, and ModelVersion with full provenance,
manifest SHA, validation threshold (0.673232), and evaluation metrics.
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


BUNDLE_DIR = REPO_ROOT / "artifacts/verified_multimodal/raw_yelpchi_multimodal_seed42_20261025T071547Z"
RUN_RECORD_PATH = REPO_ROOT / "docs/runs/raw_yelpchi_multimodal_seed42_20261025T071547Z.json"


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
        prep_key = "raw-yelpchi-multimodal-roberta-v1"
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
        snapshot_key = "raw-yelpchi-review-graph-47k-v1"
        graph_artifact_sha = manifest["files"]["serving_graph.pt"]
        # Raw dataset sha256 (training_data.csv)
        raw_manifest_path = BUNDLE_DIR / "raw_graph_manifest.json"
        if raw_manifest_path.is_file():
            raw_manifest = json.loads(raw_manifest_path.read_text())
            dataset_sha = raw_manifest["files"]["training_csv_sha256"]
            edge_counts = raw_manifest["edge_counts"]
        else:
            dataset_sha = "dbd3769b608bf249ed484f87d291e5d73f4988fd33e26f1bb96a50e8cdd418c8"
            edge_counts = {"rur": 108676, "rsr": 7997944, "rtr": 455606}

        snapshot = session.scalar(select(GraphSnapshot).where(GraphSnapshot.snapshot_key == snapshot_key))
        if snapshot is None:
            snapshot = GraphSnapshot(
                snapshot_key=snapshot_key,
                dataset_name="samygithub/collective-opinion-spam-detection",
                dataset_sha256=dataset_sha,
                artifact_uri="artifacts/verified_multimodal/raw_yelpchi_multimodal_seed42_20261025T071547Z/serving_graph.pt",
                artifact_sha256=graph_artifact_sha,
                graph_builder_version="build_yelpchi_raw_graph.py@8580a4f",
                relation_schema_version="raw_yelpchi_review_graph_v1",
                split_protocol_key="StratifiedShuffleSplit_60_20_20_seed42",
                node_count=int(model_config.get("labelled_node_count", 47176)),
                edge_counts=edge_counts,
                storage_status="available",
                batch_context_permitted=False,
                provenance="real",
            )
            session.add(snapshot)
            session.flush()
            print(f"Created GraphSnapshot: id={snapshot.graph_snapshot_id}, key={snapshot_key}")
        else:
            print(f"Existing GraphSnapshot: id={snapshot.graph_snapshot_id}, key={snapshot_key}")
        results["graph_snapshot_id"] = snapshot.graph_snapshot_id

        # 3. ModelVersion
        model_version_key = "raw-yelpchi-multimodal-roberta-gnn-seed42"
        model_ver = session.scalar(select(ModelVersion).where(ModelVersion.version_key == model_version_key))
        if model_ver is None:
            arch_config = {
                "model_config": model_config,
                "manifest_sha256": run_record["bundle_manifest_sha256"],
                "raw_graph_sha256": model_config["raw_graph_sha256"],
                "graph_snapshot_hash": graph_artifact_sha,
                "metrics": metrics_data.get("test", {}),
                "validation": {
                    "best_epoch": metrics_data.get("best_epoch"),
                    "best_validation_f1_macro": metrics_data.get("best_validation_f1_macro"),
                    "selected_validation_threshold": metrics_data.get("selected_validation_threshold"),
                },
                "run_id": manifest["run_id"],
                "model_claim": manifest["model_claim"],
            }
            # recommended_threshold numeric(8, 7): max 8 total digits, 7 decimals
            threshold_val = round(Decimal(str(manifest["threshold"])), 7)
            model_ver = ModelVersion(
                version_key=model_version_key,
                model_name="RobertaRelationGNN",
                architecture_version="frozen_roberta_relation_specific_pyg_graphsage_cross_attention",
                architecture_config=arch_config,
                config_sha256=manifest["files"]["model_config.json"],
                checkpoint_uri="artifacts/verified_multimodal/raw_yelpchi_multimodal_seed42_20261025T071547Z/model_state.pt",
                checkpoint_sha256=manifest["files"]["model_state.pt"],
                preprocessing_version_id=prep.preprocessing_version_id,
                input_contract_version="raw_yelpchi_multimodal_v1",
                supported_inference_mode="known_node_only",
                recommended_threshold=threshold_val,
                threshold_source="Validation split F1-Macro maximization (val_f1=0.7423)",
                lifecycle_status="verified",
                provenance="real",
                verification_at=now,
            )
            session.add(model_ver)
            session.flush()
            print(f"Created ModelVersion: id={model_ver.model_version_id}, key={model_version_key}")
        else:
            print(f"Existing ModelVersion: id={model_ver.model_version_id}, key={model_version_key}")
        results["model_version_id"] = model_ver.model_version_id

        session.commit()

    return results


def main() -> int:
    try:
        results = register()
        print(f"Successfully registered verified multimodal model: {results}")
        return 0
    except Exception as exc:
        print(f"Failed to register verified multimodal model: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
