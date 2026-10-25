#!/usr/bin/env python3
"""Build an honest inductive temporal review graph from labelled raw YelpChi data.

Evaluation protocol and edge policy: inductive-rur-rsr-rtr-v1
- Reviews are ordered chronologically by arrival timestamp (with stable tie-breaking).
- Features use only the node's own content and strictly historic prior activity (no future leakage).
- Edges are directed from historic context to candidate arrival (no candidate-to-historic edges).
- Each relation (RUR, RSR, RTR) is capped at the most recent 50 deterministically ordered neighbors.
- Train (60%), Validation (20%), and Test (20%) form chronological arrival windows.
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


def build_inductive_features(records: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    """Build 14 label-free features using only candidate content and strictly historic prior activity."""
    text = records.review_text.astype(str)
    chars = text.str.len().to_numpy(np.float32)
    words = text.str.split().str.len().to_numpy(np.float32)

    # Strictly historic prior counts: cumcount() in timestamp-sorted order gives prior count
    prior_reviewer_count = records.groupby("reviewer_id").cumcount().to_numpy(np.float32)
    prior_product_count = records.groupby("product_id").cumcount().to_numpy(np.float32)

    features = pd.DataFrame({
        "rating": records.rating.to_numpy(np.float32),
        "log_prior_reviewer_review_count": np.log1p(prior_reviewer_count),
        "log_prior_product_review_count": np.log1p(prior_product_count),
        "log_character_count": np.log1p(chars),
        "log_word_count": np.log1p(words),
        "uppercase_ratio": text.map(lambda value: sum(char.isupper() for char in value) / max(len(value), 1)).to_numpy(np.float32),
        "digit_ratio": text.map(lambda value: sum(char.isdigit() for char in value) / max(len(value), 1)).to_numpy(np.float32),
        "punctuation_ratio": text.map(lambda value: sum(char in "!?.,;:" for char in value) / max(len(value), 1)).to_numpy(np.float32),
        "exclamation_count": text.str.count("!").to_numpy(np.float32),
        "question_count": text.str.count(r"\?").to_numpy(np.float32),
        "month_sin": np.sin(2 * np.pi * records.date.dt.month / 12).to_numpy(np.float32),
        "month_cos": np.cos(2 * np.pi * records.date.dt.month / 12).to_numpy(np.float32),
        "weekday_sin": np.sin(2 * np.pi * records.date.dt.dayofweek / 7).to_numpy(np.float32),
        "weekday_cos": np.cos(2 * np.pi * records.date.dt.dayofweek / 7).to_numpy(np.float32),
    })

    if not np.isfinite(features.to_numpy(dtype=np.float32)).all():
        raise ValueError("non-finite metadata feature detected")

    return features.to_numpy(dtype=np.float32), list(features.columns)


def build_inductive_edges(
    records: pd.DataFrame, max_neighbors: int = 50, rtr_max_days: int = 30
) -> dict[str, np.ndarray]:
    """Construct directed historic->candidate edges under inductive-rur-rsr-rtr-v1.

    Every edge (source, target) satisfies source < target and date[source] <= date[target].
    No candidate-to-historic edges. Each relation is capped at `max_neighbors`.
    """
    node_indices = records.node_index.to_numpy(dtype=np.int64)
    dates_np = records.date.to_numpy()

    # 1. RUR: same reviewer, historic to candidate, capped at max_neighbors
    rur_src, rur_tgt = [], []
    for _, group in records.groupby("reviewer_id", sort=False):
        nodes = group.node_index.to_numpy(dtype=np.int64)
        for k in range(1, len(nodes)):
            target = nodes[k]
            sources = nodes[max(0, k - max_neighbors):k]
            rur_src.extend(sources)
            rur_tgt.extend([target] * len(sources))

    # 2. RSR: same product and rating, historic to candidate, capped at max_neighbors
    rsr_src, rsr_tgt = [], []
    for _, group in records.groupby(["product_id", "rating"], sort=False):
        nodes = group.node_index.to_numpy(dtype=np.int64)
        for k in range(1, len(nodes)):
            target = nodes[k]
            sources = nodes[max(0, k - max_neighbors):k]
            rsr_src.extend(sources)
            rsr_tgt.extend([target] * len(sources))

    # 3. RTR: same product and within 30 days, historic to candidate, capped at max_neighbors
    rtr_src, rtr_tgt = [], []
    max_timedelta = np.timedelta64(rtr_max_days, "D")
    for _, group in records.groupby("product_id", sort=False):
        nodes = group.node_index.to_numpy(dtype=np.int64)
        dates = group.date.to_numpy()
        for k in range(1, len(nodes)):
            target = nodes[k]
            target_date = dates[k]
            start_k = max(0, k - max_neighbors)
            valid = [
                nodes[p]
                for p in range(k - 1, start_k - 1, -1)
                if (target_date - dates[p]) <= max_timedelta
            ]
            rtr_src.extend(valid)
            rtr_tgt.extend([target] * len(valid))

    edges = {
        "rur": np.vstack((rur_src, rur_tgt)) if rur_tgt else np.empty((2, 0), dtype=np.int64),
        "rsr": np.vstack((rsr_src, rsr_tgt)) if rsr_tgt else np.empty((2, 0), dtype=np.int64),
        "rtr": np.vstack((rtr_src, rtr_tgt)) if rtr_tgt else np.empty((2, 0), dtype=np.int64),
    }

    # Verify strict causality invariant on every edge
    for name, edge_arr in edges.items():
        if edge_arr.shape[1] > 0:
            src = edge_arr[0]
            tgt = edge_arr[1]
            if not (src < tgt).all():
                raise ValueError(f"Temporal causality violation in {name}: found non-past edge source >= target")
            if not (dates_np[src] <= dates_np[tgt]).all():
                raise ValueError(f"Timestamp causality violation in {name}: found edge source date > target date")

    return edges


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training-csv", required=True, help="Path to labelled YelpChi training_data.csv")
    parser.add_argument("--output-dir", required=True, help="Directory to save inductive graph artifact")
    parser.add_argument("--expected-node-count", type=int, default=47176)
    parser.add_argument("--max-neighbors", type=int, default=50)
    parser.add_argument("--rtr-days", type=int, default=30)
    args = parser.parse_args()

    train_path = Path(args.training_csv).resolve()
    records = read_training_csv(train_path)
    if len(records) != args.expected_node_count:
        raise ValueError(f"expected {args.expected_node_count} labelled reviews, found {len(records)}")
    if records.review_id.duplicated().any():
        raise ValueError("raw review IDs must be globally unique")

    # Chronological sort: primary date, secondary review_id tie-break
    records = records.sort_values(["date", "review_id"], kind="stable").reset_index(drop=True)
    records["node_index"] = np.arange(len(records), dtype=np.int64)

    # Chronological splits: 60% train, 20% validation, 20% test arrival windows
    n_total = len(records)
    n_train = int(n_total * 0.6)
    n_val = int(n_total * 0.2)
    n_test = n_total - n_train - n_val

    split_membership = np.empty(n_total, dtype=object)
    split_membership[:n_train] = "train"
    split_membership[n_train:n_train + n_val] = "validation"
    split_membership[n_train + n_val:] = "test"
    records["split"] = split_membership

    # Build leak-free metadata features
    x_meta, feature_names = build_inductive_features(records)

    # Build inductive historic->candidate edges under inductive-rur-rsr-rtr-v1
    edges = build_inductive_edges(records, max_neighbors=args.max_neighbors, rtr_max_days=args.rtr_days)

    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)

    identity = records.loc[
        :,
        [
            "node_index",
            "review_id",
            "reviewer_id",
            "product_id",
            "rating",
            "date",
            "split",
            "review_text",
            "label",
            "source_file",
        ],
    ]
    identity.to_csv(output / "node_identity.csv", index=False)

    split_dates = {
        "train_window": [records.date.iloc[0].isoformat(), records.date.iloc[n_train - 1].isoformat()],
        "validation_window": [records.date.iloc[n_train].isoformat(), records.date.iloc[n_train + n_val - 1].isoformat()],
        "test_window": [records.date.iloc[n_train + n_val].isoformat(), records.date.iloc[-1].isoformat()],
    }

    graph = {
        "schema_version": 1,
        "graph_schema": "raw_yelpchi_inductive_graph_v1",
        "relation_policy": "inductive-rur-rsr-rtr-v1",
        "review_ids": records.review_id.tolist(),
        "review_text": records.review_text.tolist(),
        "dates": records.date.dt.strftime("%Y-%m-%dT%H:%M:%SZ").tolist(),
        "x_meta": torch.from_numpy(x_meta),
        "labels": torch.from_numpy(records.label.to_numpy(np.int64)),
        "edge_index_rur": torch.from_numpy(edges["rur"]).long(),
        "edge_index_rsr": torch.from_numpy(edges["rsr"]).long(),
        "edge_index_rtr": torch.from_numpy(edges["rtr"]).long(),
        "splits": {
            "train": list(range(0, n_train)),
            "validation": list(range(n_train, n_train + n_val)),
            "test": list(range(n_train + n_val, n_total)),
        },
        "split_dates": split_dates,
    }
    torch.save(graph, output / "inductive_graph.pt")

    files = {
        "training_csv_sha256": sha256(train_path),
        "node_identity_sha256": sha256(output / "node_identity.csv"),
        "inductive_graph_sha256": sha256(output / "inductive_graph.pt"),
    }

    manifest = {
        "schema_version": 1,
        "bundle_type": "raw_yelpchi_inductive_graph",
        "model_family": "raw_yelpchi_inductive_roberta_gnn_v1",
        "relation_policy": "inductive-rur-rsr-rtr-v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "provenance": "raw_csv_labelled_training_split",
        "node_count": n_total,
        "node_order": "chronological date with review_id tie-break",
        "label_mapping": {"Y": 1, "N": 0},
        "rating_column_contract": "rating_OhNo",
        "feature_names": feature_names,
        "max_neighbors_per_relation": args.max_neighbors,
        "relations": {
            "rur": "same reviewer, historic to candidate, capped at 50",
            "rsr": "same product and rating, historic to candidate, capped at 50",
            "rtr": f"same product within {args.rtr_days} days, historic to candidate, capped at 50",
        },
        "edge_counts": {name: int(value.shape[1]) for name, value in edges.items()},
        "splits": {
            "train_nodes": n_train,
            "validation_nodes": n_val,
            "test_nodes": n_test,
            "windows": split_dates,
        },
        "files": files,
    }
    (output / "graph_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    print(
        json.dumps(
            {
                "output_dir": str(output),
                "node_count": n_total,
                "edge_counts": manifest["edge_counts"],
                "graph_sha256": files["inductive_graph_sha256"],
                "splits": manifest["splits"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
