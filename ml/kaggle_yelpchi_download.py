#!/usr/bin/env python3
"""Download one explicitly named Kaggle dataset and record its local provenance.

This script intentionally does not contain a Kaggle credential or a hard-coded
dataset owner.  The caller supplies the exact dataset reference after checking
its source, licence, and contents.  Raw files stay below ``backend/data`` and
are ignored by Git.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_mat_file(output_dir: Path) -> Path:
    candidates = sorted(output_dir.rglob("*.mat"))
    if len(candidates) != 1:
        rendered = ", ".join(str(item) for item in candidates) or "none"
        raise RuntimeError(
            "Expected exactly one .mat file after download; found " + rendered
        )
    return candidates[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-ref", required=True, help="Kaggle ref: owner/dataset-slug")
    parser.add_argument("--output-dir", default="backend/data/yelpchi")
    parser.add_argument(
        "--source-url",
        required=True,
        help="Canonical source or Kaggle dataset URL recorded in acquisition.json",
    )
    parser.add_argument("--expected-sha256", help="Optional trusted SHA256 of YelpChi.mat; mismatch fails closed")
    args = parser.parse_args()

    if not os.environ.get("KAGGLE_API_TOKEN") and not os.environ.get("KAGGLE_USERNAME"):
        raise RuntimeError("Kaggle credentials are not available in the environment.")

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    kaggle_command = shutil.which("kaggle")
    if kaggle_command is None:
        raise RuntimeError("Kaggle CLI is not on PATH. Install it in the active environment: python -m pip install kaggle")
    command = [
        kaggle_command,
        "datasets",
        "download",
        args.dataset_ref,
        "--path",
        str(output_dir),
        "--unzip",
    ]
    subprocess.run(command, check=True)

    mat_path = find_mat_file(output_dir)
    canonical_path = output_dir / "YelpChi.mat"
    if mat_path.resolve() != canonical_path.resolve():
        shutil.copy2(mat_path, canonical_path)
        mat_path = canonical_path

    dataset_hash = sha256(mat_path)
    if args.expected_sha256 and dataset_hash.lower() != args.expected_sha256.lower():
        raise RuntimeError("Downloaded YelpChi.mat SHA256 does not match --expected-sha256")
    record = {
        "schema_version": 1,
        "dataset_ref": args.dataset_ref,
        "source_url": args.source_url,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_file": mat_path.name,
        "dataset_sha256": dataset_hash,
        "credential_used": "environment_only_not_recorded",
    }
    record_path = output_dir / "acquisition.json"
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"mat_path": str(mat_path), "acquisition": str(record_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
