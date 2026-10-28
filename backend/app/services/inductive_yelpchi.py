"""Verified inductive YelpChi runtime for live CSV batch scoring.

This runtime implements the leak-free inductive replay serving contract:
1. Verifies the Kaggle bundle manifest and all constituent checksums against the committed run record.
2. Verifies local fixed-review reproduction before accepting live scoring requests.
3. Loads exact tokenizer, RoBERTa revision, StandardScaler, PyG RobertaRelationGNN, and inductive-rur-rsr-rtr-v1 policy.
4. Queries historical context without selecting ground_truth_label or label_source.
5. Builds strictly directed historic-to-uploaded edges (capped at 50 neighbors per relation).
6. Computes RoBERTa embeddings in bounded batches and scores only uploaded nodes.
7. Produces authentic relation attention weights and tamper-evident SHA256 evidence.
8. Leaves historical snapshots completely immutable.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import torch

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.models.roberta_relation_gnn import RobertaRelationGNN
from app.models import GraphSnapshot
from app.services.batch_csv import BatchReviewInput, PermittedHistoricContext
from app.services.inductive_relations import node_order, stitch_arrivals

logger = logging.getLogger("neurograph.inductive_runtime")

DEFAULT_INDUCTIVE_BUNDLE = REPO_ROOT / "artifacts/verified_inductive/raw_yelpchi_inductive_seed42_20261025T125837Z"
DEFAULT_INDUCTIVE_RUN_RECORD = REPO_ROOT / "docs/runs/raw_yelpchi_inductive_seed42_20261025T125837Z.json"

REQUIRED_BUNDLE_FILES = (
    "model_state.pt",
    "model_config.json",
    "preprocessing.json",
    "serving_graph.pt",
    "metrics.json",
    "training_log.json",
    "evaluation_targets.npz",
    "fixed_review_reproduction.json",
)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class BundleVerificationError(Exception):
    """Raised when bundle manifest, file checksums, or reproduction checks fail."""


class ScopeIncompatibilityError(Exception):
    """Raised when snapshot scope key or relation schema does not match model expectations."""


class InsufficientContextError(Exception):
    """Raised when the selected snapshot has no eligible historic context for scoring."""


@dataclass(frozen=True)
class ScoredReviewWithEvidence:
    review_id: int
    risk_score: float
    predicted_label: int
    attention_weights: dict[str, float]
    graph_snapshot_id: int
    relation_schema_version: str
    context_cutoff_at: datetime
    neighbor_counts: dict[str, int]
    historic_review_ids: list[int]
    stitched_graph_sha256: str
    input_feature_sha256: str
    embedding_sha256: str
    bundle_manifest_sha256: str
    provenance: str = "real"


class InductiveYelpChiRuntime:
    """Singleton-capable runtime verifying and serving raw_yelpchi_inductive_roberta_gnn_v1."""

    def __init__(
        self,
        bundle_dir: Path | None = None,
        run_record_path: Path | None = None,
        device: str = "cpu",
    ):
        self.bundle_dir = (bundle_dir or DEFAULT_INDUCTIVE_BUNDLE).resolve()
        self.run_record_path = (run_record_path or DEFAULT_INDUCTIVE_RUN_RECORD).resolve()
        self.device = torch.device(device)
        self._lock = threading.Lock()
        self._verified = False
        self._manifest: dict[str, Any] | None = None
        self._manifest_sha: str | None = None
        self._model_config: dict[str, Any] | None = None
        self._prep_config: dict[str, Any] | None = None
        self._model: RobertaRelationGNN | None = None
        self._scaler_mean: np.ndarray | None = None
        self._scaler_scale: np.ndarray | None = None
        self._threshold: float = 0.787071
        self._serving_graph: dict[str, Any] | None = None
        self._serving_review_id_to_idx: dict[str, int] = {}
        self._tokenizer: Any = None
        self._hf_roberta: Any = None

    @property
    def is_verified(self) -> bool:
        return self._verified

    @property
    def threshold(self) -> float:
        return self._threshold

    @property
    def manifest_sha(self) -> str | None:
        return self._manifest_sha

    def verify_and_load(self) -> None:
        """Run all checksum and reproduction checks, then load weights into memory."""
        with self._lock:
            if self._verified:
                return

            manifest_path = self.bundle_dir / "run_manifest.json"
            if not manifest_path.is_file():
                raise BundleVerificationError(f"Bundle manifest missing at: {manifest_path}")
            if not self.run_record_path.is_file():
                raise BundleVerificationError(f"Run record missing at: {self.run_record_path}")

            manifest_content = json.loads(manifest_path.read_text())
            run_record = json.loads(self.run_record_path.read_text())
            manifest_sha = _file_sha256(manifest_path)

            if manifest_sha != run_record.get("bundle_manifest_sha256"):
                raise BundleVerificationError("Bundle manifest SHA256 mismatch with committed run record.")

            if manifest_content.get("bundle_type") != "raw_yelpchi_inductive_roberta_gnn_v1":
                raise BundleVerificationError(f"Incompatible bundle_type: {manifest_content.get('bundle_type')}")
            if manifest_content.get("provenance") != "real_benchmark_data":
                raise BundleVerificationError("Bundle provenance is not eligible for verified live serving.")

            # Check all constituent files
            for filename in REQUIRED_BUNDLE_FILES:
                target_file = self.bundle_dir / filename
                if not target_file.is_file():
                    raise BundleVerificationError(f"Required bundle file missing: {filename}")
                expected_sha = manifest_content["files"].get(filename)
                observed_sha = _file_sha256(target_file)
                if expected_sha != observed_sha:
                    raise BundleVerificationError(f"Checksum mismatch for {filename}: expected {expected_sha}, got {observed_sha}")

            # Audit serving graph for label leaks
            serving_graph = torch.load(self.bundle_dir / "serving_graph.pt", map_location="cpu", weights_only=False)
            forbidden = {"y", "labels", "train_mask", "validation_mask", "test_mask"}.intersection(serving_graph)
            if forbidden:
                raise BundleVerificationError(f"Label leakage in serving graph: {forbidden}")

            # Load model config and checkpoint
            model_config = json.loads((self.bundle_dir / "model_config.json").read_text())
            prep_config = json.loads((self.bundle_dir / "preprocessing.json").read_text())
            checkpoint = torch.load(self.bundle_dir / "model_state.pt", map_location=self.device, weights_only=False)

            model = RobertaRelationGNN(
                text_dim=int(model_config["text_dim"]),
                meta_dim=int(model_config["meta_dim"]),
                hidden_dim=int(model_config["hidden_dim"]),
                dropout=float(model_config["dropout"]),
            ).to(self.device)
            model.load_state_dict(checkpoint["state_dict"], strict=True)
            model.eval()

            # Verify fixed review reproduction
            fixed = manifest_content["fixed_review"]
            node_idx = int(fixed["node_index"])
            edges = {name: serving_graph[f"edge_index_{name}"].to(self.device) for name in model_config["relations"]}
            with torch.inference_mode():
                logits = model(serving_graph["x_text"].to(self.device), serving_graph["x_meta"].to(self.device), edges)
                scores = torch.softmax(logits, dim=1)[:, 1].cpu().numpy()

            observed_score = float(scores[node_idx])
            expected_score = float(fixed["expected_fraud_score"])
            tolerance = float(fixed["tolerance"])
            if abs(observed_score - expected_score) > tolerance:
                raise BundleVerificationError(
                    f"Fixed review reproduction failed: expected {expected_score}, got {observed_score}, tolerance {tolerance}"
                )

            # Preprocessing scaler
            scaler_meta = prep_config["metadata_scaler"]
            self._scaler_mean = np.array(scaler_meta["mean"], dtype=np.float32)
            self._scaler_scale = np.array(scaler_meta["scale"], dtype=np.float32)

            self._manifest = manifest_content
            self._manifest_sha = manifest_sha
            self._model_config = model_config
            self._prep_config = prep_config
            self._model = model
            self._threshold = float(manifest_content.get("threshold", 0.787071))
            self._serving_graph = serving_graph
            self._serving_review_id_to_idx = {
                rid: idx for idx, rid in enumerate(serving_graph["review_ids"])
            }
            self._verified = True
            logger.info("InductiveYelpChiRuntime verified successfully. Run ID: %s", manifest_content.get("run_id"))

    def encode_texts(self, texts: Sequence[str], batch_size: int = 32) -> torch.Tensor:
        """Encode review texts into 768-dimensional RoBERTa embeddings in bounded batches."""
        if not texts:
            return torch.empty((0, 768), dtype=torch.float32)

        # Lazy load tokenizer and HuggingFace backbone
        if self._tokenizer is None or self._hf_roberta is None:
            try:
                from transformers import AutoModel, AutoTokenizer

                tok_cfg = self._prep_config["text"]
                model_name = tok_cfg.get("model_name", "FacebookAI/roberta-base")
                revision = tok_cfg.get("resolved_revision", tok_cfg.get("requested_revision"))
                self._tokenizer = AutoTokenizer.from_pretrained(model_name, revision=revision, use_fast=True)
                self._hf_roberta = AutoModel.from_pretrained(model_name, revision=revision).to(self.device)
                self._hf_roberta.eval()
            except Exception as e:
                self._tokenizer = None
                self._hf_roberta = None
                raise BundleVerificationError(
                    "The pinned RoBERTa encoder could not be loaded. No predictions were generated; "
                    "install the text-model dependencies and make the verified model revision available."
                ) from e

        if self._tokenizer is not None and self._hf_roberta is not None:
            vectors: list[torch.Tensor] = []
            max_len = int(self._prep_config["text"].get("max_length", 192))
            for i in range(0, len(texts), batch_size):
                chunk = list(texts[i : i + batch_size])
                tokens = self._tokenizer(chunk, max_length=max_len, padding=True, truncation=True, return_tensors="pt").to(self.device)
                with torch.inference_mode():
                    outputs = self._hf_roberta(**tokens)
                    mask = tokens["attention_mask"].unsqueeze(-1)
                    pooled = (outputs.last_hidden_state * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
                vectors.append(pooled.cpu())
            return torch.cat(vectors, dim=0)

        raise BundleVerificationError("Pinned RoBERTa encoder is unavailable; scoring is blocked.")

    def build_meta_features(
        self,
        uploaded_reviews: Sequence[BatchReviewInput],
        historic_reviews: Sequence[BatchReviewInput],
    ) -> torch.Tensor:
        """Construct the 14 scaled metadata features using cumulative past counts and text statistics."""
        # Count prior occurrences in historic reviews
        hist_reviewer_counts: dict[int, int] = {}
        hist_product_counts: dict[int, int] = {}
        for r in historic_reviews:
            hist_reviewer_counts[r.reviewer_id] = hist_reviewer_counts.get(r.reviewer_id, 0) + 1
            hist_product_counts[r.product_id] = hist_product_counts.get(r.product_id, 0) + 1

        feature_matrix = []
        # In-batch cumulative tracker for sequential arrivals inside batch
        batch_reviewer_counts: dict[int, int] = {}
        batch_product_counts: dict[int, int] = {}

        for rev in uploaded_reviews:
            rid = rev.reviewer_id
            pid = rev.product_id
            prior_reviewer = hist_reviewer_counts.get(rid, 0) + batch_reviewer_counts.get(rid, 0)
            prior_product = hist_product_counts.get(pid, 0) + batch_product_counts.get(pid, 0)
            batch_reviewer_counts[rid] = batch_reviewer_counts.get(rid, 0) + 1
            batch_product_counts[pid] = batch_product_counts.get(pid, 0) + 1

            text = rev.review_text or ""
            chars = float(len(text))
            words = float(len(text.split()))
            upper_ratio = sum(c.isupper() for c in text) / max(len(text), 1)
            digit_ratio = sum(c.isdigit() for c in text) / max(len(text), 1)
            punct_ratio = sum(c in "!?.,;:" for c in text) / max(len(text), 1)
            excl_count = float(text.count("!"))
            quest_count = float(text.count("?"))

            dt = rev.reviewed_at
            month_sin = np.sin(2 * np.pi * dt.month / 12)
            month_cos = np.cos(2 * np.pi * dt.month / 12)
            weekday_sin = np.sin(2 * np.pi * dt.weekday() / 7)
            weekday_cos = np.cos(2 * np.pi * dt.weekday() / 7)

            raw_row = [
                float(rev.rating),
                float(np.log1p(prior_reviewer)),
                float(np.log1p(prior_product)),
                float(np.log1p(chars)),
                float(np.log1p(words)),
                float(upper_ratio),
                float(digit_ratio),
                float(punct_ratio),
                float(excl_count),
                float(quest_count),
                float(month_sin),
                float(month_cos),
                float(weekday_sin),
                float(weekday_cos),
            ]
            feature_matrix.append(raw_row)

        raw_np = np.array(feature_matrix, dtype=np.float32)
        scaled_np = (raw_np - self._scaler_mean) / self._scaler_scale
        return torch.from_numpy(scaled_np)

    def score_batch(
        self,
        uploaded_reviews: Sequence[BatchReviewInput],
        historic_context: PermittedHistoricContext,
        snapshot: GraphSnapshot,
    ) -> list[ScoredReviewWithEvidence]:
        """Score uploaded reviews against permitted historic context without modifying snapshots."""
        if not self._verified:
            self.verify_and_load()

        if not uploaded_reviews:
            return []

        # Scope compatibility verification
        expected_policy = self._prep_config.get("relation_policy", "inductive-rur-rsr-rtr-v1")
        if snapshot.context_scope_key != expected_policy and snapshot.relation_schema_version != expected_policy:
            raise ScopeIncompatibilityError(
                f"Snapshot scope '{snapshot.context_scope_key}' does not match model policy '{expected_policy}'."
            )

        if not historic_context.reviews:
            raise InsufficientContextError("The selected graph snapshot contains insufficient historical context.")

        # Temporal causality: historic context cutoff
        context_cutoff_at = min(r.reviewed_at for r in uploaded_reviews)
        filtered_historic = [r for r in historic_context.reviews if r.reviewed_at <= context_cutoff_at]
        if not filtered_historic:
            raise InsufficientContextError(
                f"No historic reviews found strictly before candidate arrival cutoff {context_cutoff_at.isoformat()}."
            )

        # Sort nodes chronologically
        sorted_historic = sorted(filtered_historic, key=node_order)
        sorted_uploaded = sorted(uploaded_reviews, key=node_order)

        n_hist = len(sorted_historic)
        n_up = len(sorted_uploaded)
        max_neighbors = int(self._model_config.get("max_neighbors_per_relation", 50))

        # Reuse the training-time arrival rule: earlier rows in this same file
        # become context for later rows, without changing the frozen snapshot.
        pairs, per_review_neighbors = stitch_arrivals(sorted_historic, sorted_uploaded, max_neighbors)
        rur_src = [a for a, b in pairs["rur"]]
        rur_tgt = [b for a, b in pairs["rur"]]
        rsr_src = [a for a, b in pairs["rsr"]]
        rsr_tgt = [b for a, b in pairs["rsr"]]
        rtr_src = [a for a, b in pairs["rtr"]]
        rtr_tgt = [b for a, b in pairs["rtr"]]
        edge_index_rur = torch.tensor([rur_src, rur_tgt], dtype=torch.long)
        edge_index_rsr = torch.tensor([rsr_src, rsr_tgt], dtype=torch.long)
        edge_index_rtr = torch.tensor([rtr_src, rtr_tgt], dtype=torch.long)

        edges = {
            "rur": edge_index_rur.to(self.device),
            "rsr": edge_index_rsr.to(self.device),
            "rtr": edge_index_rtr.to(self.device),
        }

        # Calculate stitched graph SHA256
        edge_hash_data = {
            "rur": rur_src + rur_tgt,
            "rsr": rsr_src + rsr_tgt,
            "rtr": rtr_src + rtr_tgt,
            "n_hist": n_hist,
            "n_up": n_up,
        }
        stitched_graph_sha256 = hashlib.sha256(json.dumps(edge_hash_data, sort_keys=True).encode()).hexdigest()

        # Database IDs are unrelated to raw benchmark IDs. Always encode the
        # uploaded text; never reuse a tensor because an integer ID happens to match.
        uploaded_texts = [r.review_text or "" for r in sorted_uploaded]
        x_text_uploaded = self.encode_texts(uploaded_texts, batch_size=32)

        # Historic text embeddings from precomputed serving graph
        hist_emb_list = []
        for r in sorted_historic:
            s_idx = self._serving_review_id_to_idx.get(r.source_review_key) if r.source_review_key else None
            if s_idx is not None and self._serving_graph is not None:
                hist_emb_list.append(self._serving_graph["x_text"][s_idx : s_idx + 1])
            else:
                raise InsufficientContextError("Historical review lacks a verified raw-ID mapping to the selected benchmark snapshot.")
        x_text_hist = torch.cat(hist_emb_list, dim=0) if hist_emb_list else torch.zeros((0, 768), dtype=torch.float32)

        x_text = torch.cat([x_text_hist, x_text_uploaded], dim=0).to(self.device)

        # Meta features
        x_meta_uploaded = self.build_meta_features(sorted_uploaded, sorted_historic)
        # Historic meta features from serving graph if present, else default zero/scale
        hist_meta_list = []
        for r in sorted_historic:
            s_idx = self._serving_review_id_to_idx.get(r.source_review_key) if r.source_review_key else None
            if s_idx is not None and self._serving_graph is not None:
                hist_meta_list.append(self._serving_graph["x_meta"][s_idx : s_idx + 1])
            else:
                raise InsufficientContextError("Historical metadata lacks a verified raw-ID mapping to the selected benchmark snapshot.")
        x_meta_hist = torch.cat(hist_meta_list, dim=0) if hist_meta_list else torch.zeros((0, 14), dtype=torch.float32)

        x_meta = torch.cat([x_meta_hist, x_meta_uploaded], dim=0).to(self.device)

        # Execute model forward pass
        with torch.inference_mode():
            logits, attention = self._model(x_text, x_meta, edges, return_attention=True)
            probabilities = torch.softmax(logits, dim=1)[:, 1].cpu().numpy()
            attention_np = attention.cpu().numpy()

        results: list[ScoredReviewWithEvidence] = []
        for u_idx, u_rev in enumerate(sorted_uploaded):
            global_node_idx = n_hist + u_idx
            score = float(probabilities[global_node_idx])
            pred_label = 1 if score >= self._threshold else 0

            attn = {
                "rur": float(attention_np[global_node_idx, 0]),
                "rsr": float(attention_np[global_node_idx, 1]),
                "rtr": float(attention_np[global_node_idx, 2]),
            }

            u_rev_id = u_rev.review_id
            neigh = per_review_neighbors.get(u_rev_id, {"rur": [], "rsr": [], "rtr": []})
            neighbor_counts = {k: len(v) for k, v in neigh.items()}
            # Union of connected historic review IDs, capped
            all_connected = sorted(set(neigh["rur"] + neigh["rsr"] + neigh["rtr"]))

            # Evidence SHA256 hashes
            emb_bytes = x_text_uploaded[u_idx].cpu().numpy().tobytes()
            embedding_sha256 = hashlib.sha256(emb_bytes).hexdigest()

            feat_bytes = x_meta_uploaded[u_idx].cpu().numpy().tobytes()
            input_feature_sha256 = hashlib.sha256(feat_bytes).hexdigest()

            results.append(
                ScoredReviewWithEvidence(
                    review_id=u_rev.review_id,
                    risk_score=score,
                    predicted_label=pred_label,
                    attention_weights=attn,
                    graph_snapshot_id=snapshot.graph_snapshot_id,
                    relation_schema_version=expected_policy,
                    context_cutoff_at=u_rev.reviewed_at,
                    neighbor_counts=neighbor_counts,
                    historic_review_ids=all_connected,
                    stitched_graph_sha256=stitched_graph_sha256,
                    input_feature_sha256=input_feature_sha256,
                    embedding_sha256=embedding_sha256,
                    bundle_manifest_sha256=self._manifest_sha or "",
                    provenance="real",
                )
            )

        return results


_GLOBAL_INDUCTIVE_RUNTIME: InductiveYelpChiRuntime | None = None


def get_inductive_runtime() -> InductiveYelpChiRuntime:
    global _GLOBAL_INDUCTIVE_RUNTIME
    if _GLOBAL_INDUCTIVE_RUNTIME is None:
        runtime = InductiveYelpChiRuntime()
        runtime.verify_and_load()
        _GLOBAL_INDUCTIVE_RUNTIME = runtime
    return _GLOBAL_INDUCTIVE_RUNTIME
