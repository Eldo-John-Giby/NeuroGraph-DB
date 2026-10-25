#!/usr/bin/env python3
"""Prove (or reject) a CSV-text to YelpChi-MAT node mapping.

The 45,954-node YelpChi MAT benchmark does not contain review identifiers.
Therefore CSV row order, matching label counts, and similar row counts are
never evidence of alignment.  This program accepts an *authoritative* mapping
file produced by the same preprocessing pipeline that created the MAT graph,
then validates its bijection, identifiers, labels, and hashes.  It exits
non-zero and writes a report when that evidence is unavailable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy import io


CANONICAL_COLUMNS = {
    "review_id": {"review id", "review_id", "reviewid", "review"},
    "reviewer_id": {"reviewer id", "reviewer_id", "reviewerid", "user id", "user_id", "userid"},
    "product_id": {"product id", "product_id", "productid", "business id", "business_id", "item id", "item_id"},
    "review_text": {"reviews", "review text", "review_text", "text", "content"},
    "label": {"label", "labels", "spam", "is_spam", "ground_truth"},
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalise(name: object) -> str:
    return " ".join(str(name).replace("_", " ").replace("-", " ").lower().split())


def resolve_columns(frame: pd.DataFrame, required: Iterable[str], source: str) -> dict[str, str]:
    normalized = {normalise(column): str(column) for column in frame.columns}
    resolved: dict[str, str] = {}
    missing: list[str] = []
    for canonical in required:
        candidate = next((normalized[key] for key in CANONICAL_COLUMNS[canonical] if key in normalized), None)
        if candidate is None:
            missing.append(canonical)
        else:
            resolved[canonical] = candidate
    if missing:
        raise ValueError(f"{source} is missing canonical columns: {', '.join(missing)}; found {list(frame.columns)}")
    return resolved


def canonical_csv(paths: list[Path]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in paths:
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        columns = resolve_columns(frame, ("review_id", "reviewer_id", "product_id", "review_text", "label"), str(path))
        selected = pd.DataFrame({name: frame[column].astype(str).str.strip() for name, column in columns.items()})
        selected["source_file"] = path.name
        frames.append(selected)
    combined = pd.concat(frames, ignore_index=True)
    for column in ("review_id", "reviewer_id", "product_id", "review_text", "label"):
        if (combined[column] == "").any():
            raise ValueError(f"CSV has empty {column} values")
    if combined.review_id.duplicated().any():
        duplicate = combined.loc[combined.review_id.duplicated(), "review_id"].iloc[0]
        raise ValueError(f"review_id is not globally unique; first duplicate: {duplicate!r}")
    numeric_labels = pd.to_numeric(combined.label, errors="raise").astype(np.int64)
    if not set(numeric_labels.unique()).issubset({0, 1}):
        raise ValueError("CSV labels must already use binary 0/1 semantics; do not silently invert labels")
    combined["label"] = numeric_labels
    return combined


def write_report(path: Path, payload: dict, exit_code: int) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": payload["status"], "report": str(path), "reason": payload.get("reason")}, indent=2))
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mat-path", required=True)
    parser.add_argument("--training-csv", required=True)
    parser.add_argument("--testing-csv", required=True)
    parser.add_argument(
        "--node-index-map",
        help="Authoritative CSV with node_index, review_id, reviewer_id, product_id and label. "
        "It must have been emitted when the MAT graph was created.",
    )
    parser.add_argument("--output-report", required=True)
    parser.add_argument("--output-alignment", help="Written only after verification succeeds")
    args = parser.parse_args()

    output = Path(args.output_report).resolve()
    mat_path = Path(args.mat_path).resolve()
    csv_paths = [Path(args.training_csv).resolve(), Path(args.testing_csv).resolve()]
    base = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "rejected",
        "mat_path": str(mat_path),
        "csv_paths": [str(path) for path in csv_paths],
    }
    try:
        if not mat_path.is_file() or any(not path.is_file() for path in csv_paths):
            raise FileNotFoundError("MAT and both CSV paths must exist")
        raw = io.loadmat(mat_path)
        raw_features = raw["features"]
        features = raw_features.toarray() if hasattr(raw_features, "toarray") else np.asarray(raw_features)
        labels = np.asarray(raw["label"]).reshape(-1).astype(np.int64)
        if features.ndim != 2 or labels.shape[0] != features.shape[0]:
            raise ValueError("MAT features and labels are not node-aligned")
        records = canonical_csv(csv_paths)
        base.update({
            "mat_sha256": sha256(mat_path),
            "mat_node_count": int(features.shape[0]),
            "csv_row_count": int(len(records)),
            "csv_sha256": {str(path): sha256(path) for path in csv_paths},
        })
    except Exception as exc:
        base["reason"] = f"input_contract_error: {exc}"
        return write_report(output, base, 2)

    if not args.node_index_map:
        base["reason"] = (
            "no_authoritative_node_index_map: MAT has no review_id field, so row order and labels cannot establish "
            "a CSV-to-node mapping. Obtain the graph builder's index map or rebuild a new graph from the raw CSV."
        )
        return write_report(output, base, 3)

    map_path = Path(args.node_index_map).resolve()
    try:
        mapping_raw = pd.read_csv(map_path, dtype=str, keep_default_na=False)
        normalized = {normalise(column): str(column) for column in mapping_raw.columns}
        required = ("node index", "review id", "reviewer id", "product id", "label")
        missing = [name for name in required if name not in normalized]
        if missing:
            raise ValueError("node index map missing columns: " + ", ".join(missing))
        mapping = pd.DataFrame({
            "node_index": pd.to_numeric(mapping_raw[normalized["node index"]], errors="raise").astype(np.int64),
            "review_id": mapping_raw[normalized["review id"]].astype(str).str.strip(),
            "reviewer_id": mapping_raw[normalized["reviewer id"]].astype(str).str.strip(),
            "product_id": mapping_raw[normalized["product id"]].astype(str).str.strip(),
            "label": pd.to_numeric(mapping_raw[normalized["label"]], errors="raise").astype(np.int64),
        })
        expected_indices = np.arange(features.shape[0], dtype=np.int64)
        if len(mapping) != len(expected_indices) or not np.array_equal(np.sort(mapping.node_index.to_numpy()), expected_indices):
            raise ValueError("node_index must be an exact bijection over 0..N-1")
        if mapping.review_id.duplicated().any() or mapping.node_index.duplicated().any():
            raise ValueError("node-index map must have unique node_index and review_id")
        if not set(mapping.label.unique()).issubset({0, 1}):
            raise ValueError("node-index map labels must use binary 0/1 semantics")
        mapping_by_node = mapping.sort_values("node_index")
        if not np.array_equal(mapping_by_node.label.to_numpy(), labels):
            raise ValueError("node-index map labels do not exactly match MAT labels; no label inversion is attempted")
        merged = mapping.merge(records, on=["review_id", "reviewer_id", "product_id", "label"], how="inner", validate="one_to_one")
        if len(merged) != len(mapping) or len(merged) != len(records):
            raise ValueError(
                "CSV and node-index map are not an exact same-review set; "
                f"map={len(mapping)}, csv={len(records)}, exact_join={len(merged)}"
            )
        if merged.review_text.eq("").any():
            raise ValueError("verified alignment has empty review text")
        if not args.output_alignment:
            raise ValueError("--output-alignment is required when a mapping is supplied")
        alignment_path = Path(args.output_alignment).resolve()
        alignment_path.parent.mkdir(parents=True, exist_ok=True)
        merged = merged.sort_values("node_index").loc[:, ["node_index", "review_id", "reviewer_id", "product_id", "review_text", "label", "source_file"]]
        merged.to_csv(alignment_path, index=False)
        base.update({
            "status": "verified",
            "reason": "authoritative one-to-one node-index map, identifiers, and labels exactly match MAT and CSV inputs",
            "node_index_map": str(map_path),
            "node_index_map_sha256": sha256(map_path),
            "alignment_path": str(alignment_path),
            "alignment_sha256": sha256(alignment_path),
            "aligned_row_count": int(len(merged)),
        })
        return write_report(output, base, 0)
    except Exception as exc:
        base["reason"] = f"alignment_contract_error: {exc}"
        if map_path.is_file():
            base["node_index_map"] = str(map_path)
            base["node_index_map_sha256"] = sha256(map_path)
        return write_report(output, base, 4)


if __name__ == "__main__":
    raise SystemExit(main())
