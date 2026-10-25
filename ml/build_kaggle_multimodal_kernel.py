#!/usr/bin/env python3
"""Build a private Kaggle GPU kernel for verified YelpChi multimodal training.

The kernel accepts the structured graph, the text CSV dataset, and an optional
authoritative index-map Kaggle dataset.  It always runs alignment validation
first.  Without a verified mapping it exits before downloading RoBERTa or
training, preventing a false multimodal claim.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import shutil
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ML_ROOT = REPO_ROOT / "ml"

RUNNER = '''from __future__ import annotations
import base64, hashlib, io, json, shutil, subprocess, sys, zipfile
from pathlib import Path

PROJECT_ARCHIVE_B64 = {archive!r}
WORKING = Path("/kaggle/working/neurograph-yelpchi-multimodal")
PROJECT = WORKING / "project"
INPUT = Path("/kaggle/input")
EXPECTED_MAT_SHA256 = "fedb35a8fa539b27866244d3515a47a76b20080cdacb33112da3458fd2487b42"
ROBERTA_REVISION = {roberta_revision!r}

def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

WORKING.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(io.BytesIO(base64.b64decode(PROJECT_ARCHIVE_B64))) as z:
    z.extractall(PROJECT)
subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "torch-geometric", "transformers>=4.46,<5"], check=True)
mat_files = sorted(INPUT.rglob("YelpChi.mat"))
if len(mat_files) != 1: raise RuntimeError("expected exactly one YelpChi.mat: " + repr(mat_files))
mat_path = mat_files[0]
if sha256(mat_path) != EXPECTED_MAT_SHA256: raise RuntimeError("structured graph hash is not the verified benchmark")
training = sorted(INPUT.rglob("training_data.csv"))
testing = sorted(INPUT.rglob("testing_data.csv"))
if len(training) != 1 or len(testing) != 1: raise RuntimeError("expected exactly one training_data.csv and testing_data.csv")
maps = sorted(INPUT.rglob("node_index_map.csv"))
report, alignment = WORKING / "alignment_report.json", WORKING / "alignment.csv"
command = [sys.executable, str(PROJECT / "ml" / "verify_yelpchi_text_alignment.py"), "--mat-path", str(mat_path), "--training-csv", str(training[0]), "--testing-csv", str(testing[0]), "--output-report", str(report)]
if len(maps) == 1: command += ["--node-index-map", str(maps[0]), "--output-alignment", str(alignment)]
elif len(maps) > 1: raise RuntimeError("multiple node_index_map.csv files found")
result = subprocess.run(command, cwd=PROJECT)
if result.returncode != 0:
    raise SystemExit("ALIGNMENT_NOT_VERIFIED: see " + str(report))
subprocess.run([sys.executable, str(PROJECT / "ml" / "train_yelpchi_multimodal.py"), "--mat-path", str(mat_path), "--alignment-report", str(report), "--alignment-csv", str(alignment), "--output-root", str(WORKING / "bundles"), "--run-record-dir", str(WORKING / "run-records"), "--roberta-revision", ROBERTA_REVISION, "--device", "cuda"], check=True, cwd=PROJECT)
bundle = next((WORKING / "bundles").iterdir())
manifest_hash = sha256(bundle / "run_manifest.json")
subprocess.run([sys.executable, str(PROJECT / "ml" / "reproduce_yelpchi_multimodal_bundle.py"), "--bundle-dir", str(bundle), "--manifest-sha256", manifest_hash], check=True, cwd=PROJECT)
output = Path("/kaggle/working/neurograph-yelpchi-multimodal-output")
if output.exists(): shutil.rmtree(output)
output.mkdir(parents=True)
shutil.copytree(bundle, output / "bundle")
shutil.copy2(report, output / "alignment_report.json")
shutil.copytree(WORKING / "run-records", output / "run-records")
print(json.dumps({{"status":"passed", "output":str(output), "manifest_sha256":manifest_hash}}, indent=2))
'''


def archive_project() -> str:
    files = [
        "verify_yelpchi_text_alignment.py", "train_yelpchi_multimodal.py",
        "reproduce_yelpchi_multimodal_bundle.py",
    ]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in files:
            archive.write(ML_ROOT / name, f"ml/{name}")
        archive.write(ML_ROOT / "models" / "roberta_relation_gnn.py", "ml/models/roberta_relation_gnn.py")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kaggle-username", required=True)
    parser.add_argument("--graph-dataset-ref", required=True)
    parser.add_argument("--text-dataset-ref", default="samygithub/collective-opinion-spam-detection")
    parser.add_argument("--index-map-dataset-ref", help="Kaggle dataset holding authoritative node_index_map.csv")
    parser.add_argument("--roberta-revision", required=True, help="Immutable Hugging Face commit SHA")
    parser.add_argument("--kernel-slug", default="neurograph-yelpchi-multimodal")
    parser.add_argument("--output-dir", default=".kaggle/neurograph-yelpchi-multimodal")
    args = parser.parse_args()
    if any("/" not in ref for ref in (args.graph_dataset_ref, args.text_dataset_ref)):
        raise ValueError("Kaggle dataset refs must have owner/dataset-slug form")
    sources = [args.graph_dataset_ref, args.text_dataset_ref]
    if args.index_map_dataset_ref: sources.append(args.index_map_dataset_ref)
    output = Path(args.output_dir).resolve()
    if output.exists(): shutil.rmtree(output)
    output.mkdir(parents=True)
    metadata = {"id": f"{args.kaggle_username}/{args.kernel_slug}", "title": "NeuroGraph YelpChi Multimodal RoBERTa GNN", "code_file": "run_yelpchi_multimodal.py", "language": "python", "kernel_type": "script", "is_private": "true", "enable_gpu": "true", "enable_internet": "true", "machine_shape": "NvidiaTeslaT4", "dataset_sources": sources, "competition_sources": [], "kernel_sources": [], "model_sources": []}
    (output / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2) + "\\n")
    (output / "run_yelpchi_multimodal.py").write_text(RUNNER.format(archive=archive_project(), roberta_revision=args.roberta_revision))
    print(json.dumps({"kernel_dir": str(output), "kernel_id": metadata["id"], "dataset_sources": sources}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
