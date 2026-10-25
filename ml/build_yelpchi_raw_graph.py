#!/usr/bin/env python3
"""Build an auditable multi-relational review graph from labelled raw YelpChi data.

This creates a *new* benchmark and deliberately does not claim compatibility
with the anonymous 45,954-node YelpChi.mat graph.  Node identity is derived
from the raw review ID and is persisted alongside every node index.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch


ALIASES = {
    "review_id": {"review id", "review_id", "reviewid"},
    "reviewer_id": {"reviewer id", "reviewer_id", "reviewerid", "user id", "user_id", "userid"},
    "product_id": {"product id", "product_id", "productid", "business id", "business_id", "item id", "item_id"},
    "review_text": {"reviews", "review text", "review_text", "text", "content"},
    "label": {"label", "labels", "spam", "is_spam", "ground_truth"},
    "rating": {"rating", "rating ohno", "stars", "star rating", "review rating"},
    "date": {"date", "review date", "review_date", "time", "timestamp"},
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalise(name: object) -> str:
    return " ".join(str(name).replace("_", " ").replace("-", " ").lower().split())


def read_training_csv(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    available = {normalise(column): str(column) for column in raw.columns}
    selected: dict[str, pd.Series] = {}
    for field, aliases in ALIASES.items():
        column = next((available[name] for name in aliases if name in available), None)
        if column is None:
            raise ValueError(f"{path.name} missing {field}; columns are {list(raw.columns)}")
        selected[field] = raw[column].astype(str).str.strip()
    frame = pd.DataFrame(selected)
    if (frame == "").any().any():
        raise ValueError(f"{path.name} has empty required values")
    label_map = {"Y": 1, "N": 0, "1": 1, "0": 0}
    labels = frame["label"].str.upper().map(label_map)
    if labels.isna().any():
        values = sorted(frame.loc[labels.isna(), "label"].unique().tolist())
        raise ValueError(f"Label must contain only Y/N (or canonical 1/0); unsupported values: {values[:10]}")
    frame["label"] = labels.astype(np.int64)
    frame["rating"] = pd.to_numeric(frame["rating"], errors="raise").astype(np.float32)
    if not set(frame.label.unique()).issubset({0, 1}):
        raise ValueError("labels must be canonical binary 0/1; no automatic inversion is allowed")
    frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce")
    if frame.date.isna().any():
        raise ValueError(f"{path.name} contains dates that pandas cannot parse")
    frame["source_file"] = path.name
    return frame


def relation_edges(frame: pd.DataFrame, grouping: list[str], relation: str, max_group_size: int) -> np.ndarray:
    """Create directed R-R cliques, excluding self edges, without truncating groups."""
    edges: list[np.ndarray] = []
    for _, group in frame.groupby(grouping, sort=False, dropna=False):
        nodes = group.node_index.to_numpy(dtype=np.int64)
        if len(nodes) > max_group_size:
            raise ValueError(f"{relation} group of {len(nodes)} exceeds --max-group-size={max_group_size}; refusing to silently truncate")
        if len(nodes) > 1:
            source = np.repeat(nodes, len(nodes) - 1)
            target = np.concatenate([np.delete(nodes, index) for index in range(len(nodes))])
            edges.append(np.vstack((source, target)))
    return np.concatenate(edges, axis=1) if edges else np.empty((2, 0), dtype=np.int64)


def metadata(frame: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    text = frame.review_text.astype(str)
    chars = text.str.len().to_numpy(np.float32)
    words = text.str.split().str.len().to_numpy(np.float32)
    # All features are raw input-derived; no labels or future predictions enter this matrix.
    features = pd.DataFrame({
        "rating": frame.rating,
        "log_reviewer_review_count": np.log1p(frame.groupby("reviewer_id").review_id.transform("count")),
        "log_product_review_count": np.log1p(frame.groupby("product_id").review_id.transform("count")),
        "log_character_count": np.log1p(chars),
        "log_word_count": np.log1p(words),
        "uppercase_ratio": text.map(lambda value: sum(char.isupper() for char in value) / max(len(value), 1)),
        "digit_ratio": text.map(lambda value: sum(char.isdigit() for char in value) / max(len(value), 1)),
        "punctuation_ratio": text.map(lambda value: sum(char in "!?.,;:" for char in value) / max(len(value), 1)),
        "exclamation_count": text.str.count("!").astype(np.float32),
        "question_count": text.str.count(r"\\?").astype(np.float32),
        "month_sin": np.sin(2 * np.pi * frame.date.dt.month / 12),
        "month_cos": np.cos(2 * np.pi * frame.date.dt.month / 12),
        "weekday_sin": np.sin(2 * np.pi * frame.date.dt.dayofweek / 7),
        "weekday_cos": np.cos(2 * np.pi * frame.date.dt.dayofweek / 7),
    })
    if not np.isfinite(features.to_numpy(dtype=np.float32)).all():
        raise ValueError("non-finite metadata feature")
    return features.to_numpy(dtype=np.float32), list(features.columns)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training-csv", required=True, help="Fully labelled YelpChi training_data.csv")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-group-size", type=int, default=2000)
    parser.add_argument("--expected-node-count", type=int, default=47176)
    args = parser.parse_args()
    train_path = Path(args.training_csv).resolve()
    records = read_training_csv(train_path)
    if len(records) != args.expected_node_count:
        raise ValueError(f"expected {args.expected_node_count} labelled reviews, found {len(records)}")
    if records.review_id.duplicated().any():
        raise ValueError("raw review IDs must be globally unique")
    # Stable identity: node i is the i-th lexical review ID, independent of Kaggle extraction order.
    records = records.sort_values("review_id", kind="stable").reset_index(drop=True)
    records["node_index"] = np.arange(len(records), dtype=np.int64)
    records["month"] = records.date.dt.strftime("%Y-%m")
    x_meta, feature_names = metadata(records)
    edges = {
        "rur": relation_edges(records, ["reviewer_id"], "RUR", args.max_group_size),
        "rsr": relation_edges(records, ["product_id", "rating"], "RSR", args.max_group_size),
        "rtr": relation_edges(records, ["product_id", "month"], "RTR", args.max_group_size),
    }
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)
    identity = records.loc[:, ["node_index", "review_id", "reviewer_id", "product_id", "rating", "date", "month", "review_text", "label", "source_file"]]
    identity.to_csv(output / "node_identity.csv", index=False)
    graph = {"schema_version": 1, "graph_schema": "raw_yelpchi_review_graph_v1", "review_ids": records.review_id.tolist(), "review_text": records.review_text.tolist(), "x_meta": torch.from_numpy(x_meta), "labels": torch.from_numpy(records.label.to_numpy(np.int64)), **{f"edge_index_{name}": torch.from_numpy(value).long() for name, value in edges.items()}}
    torch.save(graph, output / "raw_graph.pt")
    files = {"training_csv_sha256": sha256(train_path), "node_identity_sha256": sha256(output / "node_identity.csv"), "raw_graph_sha256": sha256(output / "raw_graph.pt")}
    manifest = {"schema_version": 1, "bundle_type": "raw_yelpchi_multimodal_graph", "created_at_utc": datetime.now(timezone.utc).isoformat(), "provenance": "raw_csv_labelled_training_split", "node_count": int(len(records)), "node_order": "lexicographic review_id", "label_mapping": {"Y": 1, "N": 0}, "rating_column_contract": "rating_OhNo (or a documented rating alias)", "feature_names": feature_names, "relations": {"rur": "same reviewer_id", "rsr": "same product_id and rating", "rtr": "same product_id and UTC calendar month"}, "edge_counts": {name: int(value.shape[1]) for name, value in edges.items()}, "files": files}
    (output / "graph_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output_dir": str(output), "node_count": len(records), "edge_counts": manifest["edge_counts"], "graph_sha256": files["raw_graph_sha256"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
