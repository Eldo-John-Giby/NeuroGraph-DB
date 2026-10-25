"""Verified, label-free serving runtime for the labelled raw YelpChi multimodal GNN benchmark.

The downloaded Kaggle bundle is a transductive benchmark on 47,176 known reviews.
It verifies checksums, loads the frozen-RoBERTa + PyG GraphSAGE cross-attention model,
confirms the fixed review reproduction, and caches all known-node scores in memory on startup.
"""

from __future__ import annotations

import hashlib
import json
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from ml.models.roberta_relation_gnn import RobertaRelationGNN

DEFAULT_BUNDLE = REPOSITORY_ROOT / "artifacts/verified_multimodal/raw_yelpchi_multimodal_seed42_20261025T071547Z"
DEFAULT_RUN_RECORD = REPOSITORY_ROOT / "docs/runs/raw_yelpchi_multimodal_seed42_20261025T071547Z.json"
REQUIRED_FILES = (
    "model_state.pt",
    "model_config.json",
    "preprocessing.json",
    "serving_graph.pt",
    "metrics.json",
    "training_log.json",
    "evaluation_targets.npz",
    "fixed_review_reproduction.json",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class UnknownGraphNodeError(Exception):
    """Raised when one or more review IDs are not part of the verified graph snapshot."""

    def __init__(self, missing_ids: list[str]):
        self.missing_ids = missing_ids
        first_id = missing_ids[0] if missing_ids else "unknown"
        super().__init__(f"Review ID '{first_id}' is not part of verified graph snapshot.")


@dataclass(frozen=True)
class BundleMetadata:
    run_id: str
    manifest_sha256: str
    threshold: float
    metrics: dict[str, float]
    node_count: int
    config: dict[str, Any]
    fixed_review: dict[str, Any]


class VerifiedYelpChiMultimodal:
    def __init__(self, bundle_dir: Path | None = None, run_record_path: Path | None = None):
        self.bundle_dir = (bundle_dir or DEFAULT_BUNDLE).resolve()
        self.run_record_path = (run_record_path or DEFAULT_RUN_RECORD).resolve()
        self._lock = threading.Lock()
        self._metadata: BundleMetadata | None = None
        self._model: RobertaRelationGNN | None = None
        self._review_ids: list[str] | None = None
        self._node_by_id: dict[str, int] | None = None
        self._scores: torch.Tensor | None = None
        self._sorted_indices: list[int] | None = None

    def _verify(self) -> tuple[BundleMetadata, dict[str, Any]]:
        manifest_path = self.bundle_dir / "run_manifest.json"
        if not manifest_path.is_file():
            raise RuntimeError(f"Verified multimodal bundle manifest missing: {manifest_path}")
        if not self.run_record_path.is_file():
            raise RuntimeError(f"Committed multimodal run record missing: {self.run_record_path}")

        manifest = json.loads(manifest_path.read_text())
        run_record = json.loads(self.run_record_path.read_text())
        manifest_hash = _sha256(manifest_path)

        if manifest_hash != run_record.get("bundle_manifest_sha256"):
            raise RuntimeError("Bundle manifest SHA256 does not match the committed run record")
        if manifest.get("provenance") != "real_benchmark_data":
            raise RuntimeError("Bundle provenance is not eligible for serving")
        if manifest.get("bundle_type") != "raw_yelpchi_multimodal_roberta_pyg_gnn":
            raise RuntimeError("Bundle type is not eligible for verified multimodal serving")

        for name in REQUIRED_FILES:
            path = self.bundle_dir / name
            if not path.is_file():
                raise RuntimeError(f"Bundle file missing: {name}")
            expected = manifest.get("files", {}).get(name)
            if expected is None or _sha256(path) != expected:
                raise RuntimeError(f"Bundle file verification failed for: {name}")

        config = json.loads((self.bundle_dir / "model_config.json").read_text())
        metric_data = json.loads((self.bundle_dir / "metrics.json").read_text())
        metrics = metric_data.get("test", {})
        fixed_review = json.loads((self.bundle_dir / "fixed_review_reproduction.json").read_text())

        metadata = BundleMetadata(
            run_id=str(manifest["run_id"]),
            manifest_sha256=manifest_hash,
            threshold=float(manifest["threshold"]),
            metrics={key: float(metrics[key]) for key in ("roc_auc", "pr_auc", "f1_macro")},
            node_count=int(config.get("labelled_node_count", 0)),
            config=config,
            fixed_review=fixed_review,
        )
        return metadata, manifest

    def _load(self) -> BundleMetadata:
        with self._lock:
            if self._scores is not None and self._node_by_id is not None and self._metadata is not None:
                return self._metadata

            metadata, manifest = self._verify()
            graph_path = self.bundle_dir / "serving_graph.pt"
            graph = torch.load(graph_path, map_location="cpu", weights_only=False)

            forbidden = {"y", "labels", "train_mask", "validation_mask", "test_mask"}.intersection(graph)
            if forbidden:
                raise RuntimeError(f"Serving graph contains forbidden label fields: {forbidden}")

            review_ids = graph.get("review_ids")
            if not isinstance(review_ids, list) or len(review_ids) != metadata.node_count:
                raise RuntimeError(f"Serving graph node count mismatch: expected {metadata.node_count}")

            x_text = graph.get("x_text")
            x_meta = graph.get("x_meta")
            if x_text is None or x_text.shape[1] != int(metadata.config["text_dim"]):
                raise RuntimeError("Serving graph text embedding dimension mismatch")
            if x_meta is None or x_meta.shape[1] != int(metadata.config["meta_dim"]):
                raise RuntimeError("Serving graph metadata feature dimension mismatch")

            relations = tuple(metadata.config["relations"])
            edges = {rel: graph.get(f"edge_index_{rel}") for rel in relations}
            for rel, edge in edges.items():
                if edge is None or edge.ndim != 2 or edge.shape[0] != 2:
                    raise RuntimeError(f"Serving graph edge index for relation '{rel}' is invalid")

            model = RobertaRelationGNN(
                text_dim=int(metadata.config["text_dim"]),
                meta_dim=int(metadata.config["meta_dim"]),
                hidden_dim=int(metadata.config["hidden_dim"]),
                dropout=float(metadata.config["dropout"]),
            )
            checkpoint = torch.load(self.bundle_dir / "model_state.pt", map_location="cpu", weights_only=False)
            model.load_state_dict(checkpoint["state_dict"], strict=True)
            model.eval()

            # Compute and cache all scores once in memory on startup
            with torch.inference_mode():
                logits = model(x_text, x_meta, edges)
                scores = torch.softmax(logits, dim=1)[:, 1].cpu()

            # Confirm fixed review reproduction within tolerance
            fixed = manifest["fixed_review"]
            node_index = int(fixed["node_index"])
            review_id = fixed["review_id"]
            if review_ids[node_index] != review_id:
                raise RuntimeError(f"Fixed review ID mismatch: expected {review_id}, got {review_ids[node_index]}")

            observed_score = float(scores[node_index])
            expected_score = float(fixed["expected_fraud_score"])
            tolerance = float(fixed["tolerance"])
            if abs(observed_score - expected_score) > tolerance:
                raise RuntimeError(
                    f"Fixed review score reproduction failed: observed {observed_score}, expected {expected_score}, tol {tolerance}"
                )

            self._model = model
            self._scores = scores
            self._review_ids = review_ids
            self._node_by_id = {rid: idx for idx, rid in enumerate(review_ids)}
            self._metadata = BundleMetadata(
                run_id=metadata.run_id,
                manifest_sha256=metadata.manifest_sha256,
                threshold=metadata.threshold,
                metrics=metadata.metrics,
                node_count=len(review_ids),
                config=metadata.config,
                fixed_review=metadata.fixed_review,
            )
            return self._metadata

    def status(self) -> dict[str, Any]:
        try:
            if self._scores is not None and self._metadata is not None and self._node_by_id is not None:
                metadata = self._metadata
                fixed_reproduced = True
                observed_score = float(self._scores[int(metadata.fixed_review["node_index"])])
            else:
                metadata = self._load()
                fixed_reproduced = True
                observed_score = float(self._scores[int(metadata.fixed_review["node_index"])])

            return {
                "available": True,
                "runtime_loaded": self._model is not None,
                "scores_cached": self._scores is not None,
                "run_id": metadata.run_id,
                "manifest_sha256": metadata.manifest_sha256,
                "threshold": metadata.threshold,
                "metrics": metadata.metrics,
                "node_count": len(self._node_by_id) if self._node_by_id else metadata.node_count,
                "fixed_review": {
                    "review_id": metadata.fixed_review["review_id"],
                    "node_index": metadata.fixed_review["node_index"],
                    "expected_fraud_score": float(metadata.fixed_review["expected_fraud_score"]),
                    "observed_fraud_score": observed_score,
                    "tolerance": float(metadata.fixed_review["tolerance"]),
                    "reproduced": fixed_reproduced,
                },
                "mode": "transductive_known_node",
                "details": "Verified raw YelpChi multimodal GNN benchmark. Scores are restricted to the stored benchmark graph nodes.",
            }
        except Exception as exc:
            return {
                "available": False,
                "runtime_loaded": False,
                "scores_cached": False,
                "mode": "transductive_known_node",
                "details": str(exc),
            }

    def predict(self, review_ids: list[str]) -> dict[str, Any]:
        metadata = self._load()
        assert self._scores is not None and self._node_by_id is not None

        missing = [rid for rid in review_ids if rid not in self._node_by_id]
        if missing:
            raise UnknownGraphNodeError(missing)

        predictions = [
            {
                "review_id": rid,
                "node_index": self._node_by_id[rid],
                "fraud_score": float(self._scores[self._node_by_id[rid]]),
                "predicted_label": int(self._scores[self._node_by_id[rid]] >= metadata.threshold),
            }
            for rid in review_ids
        ]
        return {
            "run_id": metadata.run_id,
            "threshold": metadata.threshold,
            "mode": "transductive_known_node",
            "predictions": predictions,
        }

    def top_results(self, limit: int, offset: int) -> dict[str, Any]:
        metadata = self._load()
        assert self._scores is not None and self._review_ids is not None

        if self._sorted_indices is None:
            self._sorted_indices = torch.argsort(self._scores, descending=True).tolist()

        selected = self._sorted_indices[offset : offset + limit]
        return {
            "run_id": metadata.run_id,
            "threshold": metadata.threshold,
            "total": int(self._scores.numel()),
            "limit": limit,
            "offset": offset,
            "items": [
                {
                    "review_id": self._review_ids[idx],
                    "node_index": idx,
                    "fraud_score": float(self._scores[idx]),
                    "predicted_label": int(self._scores[idx] >= metadata.threshold),
                }
                for idx in selected
            ],
        }


_multimodal: VerifiedYelpChiMultimodal | None = None


def get_verified_multimodal() -> VerifiedYelpChiMultimodal:
    global _multimodal
    if _multimodal is None:
        from app.config import get_settings

        settings = get_settings()
        backend_root = REPOSITORY_ROOT / "backend"
        bundle_path = getattr(settings, "verified_multimodal_bundle_dir", None)
        record_path = getattr(settings, "verified_multimodal_run_record", None)
        if bundle_path is not None and not bundle_path.is_absolute():
            bundle_path = backend_root / bundle_path
        if record_path is not None and not record_path.is_absolute():
            record_path = backend_root / record_path
        _multimodal = VerifiedYelpChiMultimodal(
            bundle_dir=bundle_path,
            run_record_path=record_path,
        )
    return _multimodal
