"""Verified, label-free serving runtime for the YelpChi GNN baseline.

The downloaded Kaggle bundle is a transductive benchmark.  It may score only
its 45,954 known graph nodes; it must never be used for an uploaded CSV row.
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from torch import nn
from torch.nn import functional as F


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BUNDLE = REPOSITORY_ROOT / "artifacts/verified_baselines/kaggle_output/neurograph-yelpchi-output/bundle"
DEFAULT_RUN_RECORD = REPOSITORY_ROOT / "docs/runs/yelpchi_gnn_seed42_20261024T234034Z.json"
REQUIRED_FILES = (
    "model_state.pt", "model_config.json", "preprocessing.json", "serving_graph.pt",
    "metrics.json", "fixed_review_reproduction.json",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class MeanSAGEConv(nn.Module):
    """Portable mean GraphSAGE layer compatible with PyG's default SAGEConv."""

    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.lin_l = nn.Linear(in_channels, out_channels, bias=True)
        self.lin_r = nn.Linear(in_channels, out_channels, bias=False)

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor, chunk_size: int = 262_144) -> torch.Tensor:
        source, target = edge_index[0], edge_index[1]
        aggregate = torch.zeros_like(x)
        degree = torch.zeros((x.shape[0],), dtype=x.dtype, device=x.device)
        for start in range(0, source.numel(), chunk_size):
            end = min(start + chunk_size, source.numel())
            aggregate.index_add_(0, target[start:end], x.index_select(0, source[start:end]))
            degree.index_add_(0, target[start:end], torch.ones(end - start, dtype=x.dtype, device=x.device))
        aggregate = aggregate / degree.clamp_min(1).unsqueeze(1)
        return self.lin_l(aggregate) + self.lin_r(x)


class RelationGNNEncoder(nn.Module):
    def __init__(self, meta_dim: int, hidden_dim: int, relations: tuple[str, ...], dropout: float):
        super().__init__()
        self.relations = relations
        self.dropout = dropout
        self.input_proj = nn.Linear(meta_dim, hidden_dim)
        self.conv1_dict = nn.ModuleDict({key: MeanSAGEConv(hidden_dim, hidden_dim) for key in relations})
        self.conv2_dict = nn.ModuleDict({key: MeanSAGEConv(hidden_dim, hidden_dim) for key in relations})
        self.norms1 = nn.ModuleDict({key: nn.LayerNorm(hidden_dim) for key in relations})
        self.norms2 = nn.ModuleDict({key: nn.LayerNorm(hidden_dim) for key in relations})
        self.rel_attn_logits = nn.Parameter(torch.zeros(len(relations)))

    def forward(self, x: torch.Tensor, edges: dict[str, torch.Tensor]) -> torch.Tensor:
        h0 = F.relu(self.input_proj(x))
        h0 = F.dropout(h0, p=self.dropout, training=self.training)
        embeddings: list[torch.Tensor] = []
        for relation in self.relations:
            h1 = F.relu(self.norms1[relation](self.conv1_dict[relation](h0, edges[relation])))
            h1 = F.dropout(h1, p=self.dropout, training=self.training)
            embeddings.append(F.relu(self.norms2[relation](self.conv2_dict[relation](h1, edges[relation]))))
        weights = F.softmax(self.rel_attn_logits, dim=0)
        return (torch.stack(embeddings, dim=1) * weights.view(1, -1, 1)).sum(dim=1)


class YelpChiGNN(nn.Module):
    def __init__(self, meta_dim: int, hidden_dim: int, relations: tuple[str, ...], dropout: float):
        super().__init__()
        self.encoder = RelationGNNEncoder(meta_dim, hidden_dim, relations, dropout)
        self.classifier = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim), nn.LayerNorm(hidden_dim), nn.ReLU(),
            nn.Dropout(dropout), nn.Linear(hidden_dim, 2),
        )

    def forward(self, x: torch.Tensor, edges: dict[str, torch.Tensor]) -> torch.Tensor:
        return self.classifier(self.encoder(x, edges))


@dataclass(frozen=True)
class BundleMetadata:
    run_id: str
    manifest_sha256: str
    threshold: float
    metrics: dict[str, float]
    node_count: int
    config: dict[str, Any]


class VerifiedYelpChiBaseline:
    def __init__(self, bundle_dir: Path | None = None, run_record_path: Path | None = None):
        self.bundle_dir = (bundle_dir or DEFAULT_BUNDLE).resolve()
        self.run_record_path = (run_record_path or DEFAULT_RUN_RECORD).resolve()
        self._lock = threading.Lock()
        self._metadata: BundleMetadata | None = None
        self._model: YelpChiGNN | None = None
        self._graph: dict[str, Any] | None = None
        self._scores: torch.Tensor | None = None

    def _verify(self) -> BundleMetadata:
        manifest_path = self.bundle_dir / "run_manifest.json"
        if not manifest_path.is_file() or not self.run_record_path.is_file():
            raise RuntimeError("verified YelpChi bundle or committed run record is missing")
        manifest = json.loads(manifest_path.read_text())
        run_record = json.loads(self.run_record_path.read_text())
        manifest_hash = _sha256(manifest_path)
        if manifest_hash != run_record.get("bundle_manifest_sha256"):
            raise RuntimeError("bundle manifest does not match the committed run record")
        if manifest.get("provenance") != "real_benchmark_data" or manifest.get("bundle_type") != "yelpchi_structured_feature_gnn_baseline":
            raise RuntimeError("bundle provenance or type is not eligible for serving")
        if manifest.get("dataset", {}).get("sha256") != run_record.get("dataset_sha256"):
            raise RuntimeError("bundle dataset identity does not match the committed run record")
        for name in REQUIRED_FILES:
            path = self.bundle_dir / name
            if not path.is_file() or _sha256(path) != manifest.get("files", {}).get(name):
                raise RuntimeError(f"bundle file verification failed: {name}")
        config = json.loads((self.bundle_dir / "model_config.json").read_text())
        if config.get("feature_mode") != "structured_32_feature_only" or config.get("tokenizer", {}).get("applicable") is not False:
            raise RuntimeError("bundle is not the approved structured YelpChi baseline")
        metric_data = json.loads((self.bundle_dir / "metrics.json").read_text())
        metrics = metric_data.get("test", {})
        return BundleMetadata(
            run_id=str(manifest["run_id"]), manifest_sha256=manifest_hash, threshold=float(manifest["threshold"]),
            metrics={key: float(metrics[key]) for key in ("roc_auc", "pr_auc", "f1_macro")},
            node_count=0, config=config,
        )

    def status(self) -> dict[str, Any]:
        try:
            metadata = self._metadata or self._verify()
            return {"available": True, "runtime_loaded": self._model is not None,
                    "scores_cached": self._scores is not None, "run_id": metadata.run_id,
                    "manifest_sha256": metadata.manifest_sha256, "threshold": metadata.threshold,
                    "metrics": metadata.metrics, "mode": "transductive_known_node",
                    "details": "Verified 32-feature YelpChi GNN baseline. Scores are restricted to the stored benchmark graph nodes."}
        except Exception as exc:
            return {"available": False, "runtime_loaded": False, "scores_cached": False,
                    "mode": "transductive_known_node", "details": str(exc)}

    def _load(self) -> BundleMetadata:
        with self._lock:
            if self._model is not None and self._graph is not None and self._metadata is not None:
                return self._metadata
            metadata = self._verify()
            graph = torch.load(self.bundle_dir / "serving_graph.pt", map_location="cpu", weights_only=True)
            forbidden = {"y", "labels", "train_mask", "validation_mask", "test_mask"}.intersection(graph)
            if forbidden:
                raise RuntimeError("serving graph includes forbidden label fields")
            review_ids = graph.get("review_ids")
            if not isinstance(review_ids, list) or graph.get("x_meta").shape[1] != int(metadata.config["meta_dim"]):
                raise RuntimeError("serving graph input contract does not match model configuration")
            relations = tuple(metadata.config["relations"])
            edges = {relation: graph.get(f"edge_index_{relation}") for relation in relations}
            if any(edge is None or edge.ndim != 2 or edge.shape[0] != 2 for edge in edges.values()):
                raise RuntimeError("serving graph relation contract is invalid")
            model = YelpChiGNN(int(metadata.config["meta_dim"]), int(metadata.config["hidden_dim"]), relations, float(metadata.config["dropout"]))
            checkpoint = torch.load(self.bundle_dir / "model_state.pt", map_location="cpu", weights_only=True)
            model.load_state_dict(checkpoint["state_dict"], strict=True)
            model.eval()
            self._metadata = BundleMetadata(**{**metadata.__dict__, "node_count": len(review_ids)})
            self._model, self._graph = model, graph
            return self._metadata

    def _all_scores(self) -> tuple[BundleMetadata, torch.Tensor]:
        metadata = self._load()
        with self._lock:
            if self._scores is None:
                assert self._model is not None and self._graph is not None
                edges = {relation: self._graph[f"edge_index_{relation}"] for relation in self._metadata.config["relations"]}
                with torch.inference_mode():
                    self._scores = torch.softmax(self._model(self._graph["x_meta"], edges), dim=1)[:, 1].cpu()
            return metadata, self._scores

    def predict(self, review_ids: list[str]) -> dict[str, Any]:
        metadata, scores = self._all_scores()
        assert self._graph is not None
        node_by_id = {review_id: index for index, review_id in enumerate(self._graph["review_ids"])}
        missing = [review_id for review_id in review_ids if review_id not in node_by_id]
        if missing:
            raise KeyError(", ".join(missing[:5]))
        predictions = [{"review_id": review_id, "node_index": node_by_id[review_id],
                        "fraud_score": float(scores[node_by_id[review_id]]),
                        "predicted_label": int(scores[node_by_id[review_id]] >= metadata.threshold)} for review_id in review_ids]
        return {"run_id": metadata.run_id, "threshold": metadata.threshold, "mode": "transductive_known_node", "predictions": predictions}

    def top_results(self, limit: int, offset: int) -> dict[str, Any]:
        metadata, scores = self._all_scores()
        assert self._graph is not None
        ordering = torch.argsort(scores, descending=True)
        selected = ordering[offset: offset + limit].tolist()
        return {"run_id": metadata.run_id, "threshold": metadata.threshold, "total": int(scores.numel()),
                "limit": limit, "offset": offset, "items": [
                    {"review_id": self._graph["review_ids"][index], "node_index": index,
                     "fraud_score": float(scores[index]), "predicted_label": int(scores[index] >= metadata.threshold)}
                    for index in selected
                ]}


_baseline: VerifiedYelpChiBaseline | None = None


def get_verified_baseline() -> VerifiedYelpChiBaseline:
    global _baseline
    if _baseline is None:
        from app.config import get_settings

        settings = get_settings()
        backend_root = REPOSITORY_ROOT / "backend"
        bundle_path = settings.verified_baseline_bundle_dir
        record_path = settings.verified_baseline_run_record
        if bundle_path is not None and not bundle_path.is_absolute():
            bundle_path = backend_root / bundle_path
        if record_path is not None and not record_path.is_absolute():
            record_path = backend_root / record_path
        _baseline = VerifiedYelpChiBaseline(
            bundle_dir=bundle_path,
            run_record_path=record_path,
        )
    return _baseline
