#!/usr/bin/env python3
"""Prepare local, readable viva evidence from the actual saved split indices.

Requires NumPy and the private local dataset/artifacts. Does not train, infer,
contact cloud services, modify source data, or write credentials. Generated
datasets stay under ignored output/viva; do not commit them to GitHub.
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RUN = "raw_yelpchi_inductive_seed42_20261025T125837Z"
BUNDLE = ROOT / "artifacts/verified_inductive" / RUN
OUT = ROOT / "output/viva"


def main() -> None:
    source = ROOT / ".kaggle/yelpchi-raw/training_data.csv"
    graph = json.loads((BUNDLE / "inductive_graph_manifest.json").read_text())
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != graph["files"]["training_csv_sha256"]:
        raise ValueError("Source CSV does not match the trained graph manifest")
    with source.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        original_headers = reader.fieldnames
        rows = list(reader)
    rows.sort(key=lambda row: (datetime.strptime(row["Date"].strip(), "%m/%d/%Y"), row["review ID"].strip()))
    with np.load(BUNDLE / "evaluation_targets.npz", allow_pickle=False) as saved:
        labels = np.array([{"Y": 1, "N": 0}[row["Label"].strip().upper()] for row in rows])
        if not np.array_equal(labels, saved["labels"]):
            raise ValueError("Chronological labels do not match saved evaluation targets")
        splits = {name: saved[f"{name}_indices"].copy() for name in ("train", "validation", "test")}
    combined = np.concatenate(list(splits.values()))
    if not np.array_equal(np.sort(combined), np.arange(len(rows))):
        raise ValueError("Saved splits overlap or omit rows")
    data = OUT / "data"
    evidence = OUT / "evidence"
    data.mkdir(parents=True, exist_ok=True)
    evidence.mkdir(parents=True, exist_ok=True)
    headers = ["model_split", "chronological_node_index", *original_headers]
    summary = {
        "model_run": RUN,
        "source": str(source),
        "source_sha256": digest,
        "source_matches_saved_graph_manifest": True,
        "sorted_labels_match_saved_evaluation_targets": True,
        "row_count": len(rows),
        "labels": dict(Counter(row["Label"] for row in rows)),
        "label_mapping": {"Y": "1: dataset spam/filtered label", "N": "0: dataset nonspam/recommended label"},
        "rating_source_column": "rating_OhNo (explicit builder contract)",
        "rating_values": sorted(set(row["rating_OhNo"] for row in rows)),
        "splits": {},
        "warning": "These labelled CSVs are evaluation evidence, not fresh upload demos. The downloaded testing_data.csv has no labels and did not produce the reported test metrics.",
    }
    small = []
    for name, indices in splits.items():
        selected = [{"model_split": name, "chronological_node_index": int(i), **rows[int(i)]} for i in indices]
        filename = data / f"{name}_exact.csv"
        with filename.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            writer.writerows(selected)
        # Two examples from each label, in each split. Full original text retained.
        for label in ("N", "Y"):
            small.extend([row for row in selected if row["Label"] == label][:2])
        summary["splits"][name] = {
            "rows": len(selected),
            "labels": dict(Counter(row["Label"] for row in selected)),
            "first_date": selected[0]["Date"],
            "last_date": selected[-1]["Date"],
            "csv": str(filename),
            "csv_sha256": hashlib.sha256(filename.read_bytes()).hexdigest(),
        }
    with (data / "START_HERE_12_real_examples.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(small)
    unlabeled = ROOT / ".kaggle/yelpchi-raw/testing_data.csv"
    with unlabeled.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        summary["downloaded_unlabelled_test_file"] = {
            "path": str(unlabeled),
            "headers": reader.fieldnames,
            "rows": sum(1 for _ in reader),
            "has_Label_column": "Label" in reader.fieldnames,
            "used_for_reported_test_metrics": False,
        }
    (evidence / "dataset_and_split_proof.json").write_text(json.dumps(summary, indent=2) + "\n")
    for filename in ("metrics.json", "model_config.json", "training_log.json", "inductive_graph_manifest.json", "fixed_review_reproduction.json"):
        shutil.copyfile(BUNDLE / filename, evidence / filename)
    links = [
        ("Read the beginner viva guide", ROOT / "docs/defense/BEGINNER_VIVA_GUIDE.md"),
        ("Shared-test model comparison and results", ROOT / "docs/benchmarks/README.md"),
        ("All 12 recorded run metrics", ROOT / "docs/benchmarks/results.csv"),
        ("Start with 12 real labelled examples", data / "START_HERE_12_real_examples.csv"),
        ("Exact training rows: 28,305", data / "train_exact.csv"),
        ("Exact validation rows: 9,435", data / "validation_exact.csv"),
        ("Exact final test rows: 9,436", data / "test_exact.csv"),
        ("Verified dataset and split counts", evidence / "dataset_and_split_proof.json"),
        ("Final measured results", evidence / "metrics.json"),
        ("Model dimensions and saved settings", evidence / "model_config.json"),
        ("All 80 training rounds", evidence / "training_log.json"),
        ("Graph rules and 14 input feature names", evidence / "inductive_graph_manifest.json"),
        ("Fixed-review reproduction evidence", evidence / "fixed_review_reproduction.json"),
        ("Original downloaded labelled source", source),
        ("Database ER diagram", ROOT / "docs/submission/ERD.md"),
        ("Current demonstration route", ROOT / "docs/defense/LIVE_DEMO_SCRIPT.md"),
    ]
    (OUT / "OPEN_FIRST.md").write_text(
        "# NeuroGraph viva: open these files\n\n"
        "Prepared from the actual local source and saved split indices. No model was retrained. "
        "The three exact CSVs retain every original column and add split name and chronological node index. "
        "The 12-row file is a deliberately selected illustration, not a balanced replacement test set.\n\n"
        + "\n".join(f"- [{label}](<{path}>)" for label, path in links)
        + "\n\nDo not upload these labelled historical files as new batches: their review IDs already exist. "
        "Use the website's downloadable fresh-upload example for that demonstration. "
        "Raw data, generated CSVs and private model bundles are kept outside Git.\n"
    )
    print(json.dumps({"launcher": str(OUT / "OPEN_FIRST.md"), "proof": summary}, indent=2))


if __name__ == "__main__":
    main()
