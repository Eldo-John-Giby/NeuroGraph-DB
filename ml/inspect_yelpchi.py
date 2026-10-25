#!/usr/bin/env python3
"""Inspect a YelpChi MAT file before selecting an ML architecture.

The report is deliberately evidence based: it states whether text-like arrays
are present, verifies the structured YelpChi graph contract, and never infers
that review text exists from numeric features.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from scipy import io, sparse


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def describe(value: Any) -> dict[str, Any]:
    if sparse.issparse(value):
        return {
            "kind": "sparse_matrix",
            "shape": list(value.shape),
            "dtype": str(value.dtype),
            "nnz": int(value.nnz),
        }
    array = np.asarray(value)
    return {"kind": "ndarray", "shape": list(array.shape), "dtype": str(array.dtype)}


def looks_like_text(value: Any) -> bool:
    if sparse.issparse(value):
        return False
    array = np.asarray(value)
    return array.dtype.kind in {"U", "S", "O"} and array.size > 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mat-path", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    mat_path = Path(args.mat_path)
    if not mat_path.is_file():
        raise FileNotFoundError(mat_path)
    loaded = io.loadmat(mat_path)
    fields = {key: value for key, value in loaded.items() if not key.startswith("__")}
    report_fields = {key: describe(value) for key, value in fields.items()}
    text_keys = sorted(key for key, value in fields.items() if looks_like_text(value))
    required = ("features", "label", "net_rur", "net_rsr", "net_rtr")
    missing = [key for key in required if key not in fields]
    structured_ok = not missing
    node_count = None
    feature_count = None
    if structured_ok:
        feature_shape = tuple(fields["features"].shape)
        if len(feature_shape) == 2:
            node_count, feature_count = map(int, feature_shape)
        label_count = int(np.asarray(fields["label"]).reshape(-1).shape[0])
        structured_ok = (
            node_count is not None
            and feature_count == 32
            and label_count == node_count
            and all(tuple(fields[key].shape) == (node_count, node_count) for key in required[2:])
        )

    if text_keys:
        pipeline = "text_requires_alignment_audit"
        reason = "Text-like arrays were found, but review/node alignment must be audited before RoBERTa is allowed."
    elif structured_ok:
        pipeline = "structured_32_feature_gnn"
        reason = "No text-like arrays were found; train only the 32-feature relation-aware GNN baseline."
    else:
        pipeline = "unsupported"
        reason = "The expected YelpChi structured graph contract was not found."

    report = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "mat_path": str(mat_path),
        "mat_sha256": sha256(mat_path),
        "fields": report_fields,
        "text_like_keys": text_keys,
        "node_count": node_count,
        "feature_count": feature_count,
        "structured_graph_contract_valid": structured_ok,
        "selected_pipeline": pipeline,
        "selection_reason": reason,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"selected_pipeline": pipeline, "report": str(output)}, indent=2))
    return 0 if pipeline != "unsupported" else 2


if __name__ == "__main__":
    raise SystemExit(main())
