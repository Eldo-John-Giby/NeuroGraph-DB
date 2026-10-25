#!/usr/bin/env python3
"""Build a Kaggle GPU kernel for the authoritative raw-CSV YelpChi benchmark."""

from __future__ import annotations

import argparse
import base64
import io
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ML = ROOT / "ml"

RUNNER = '''from __future__ import annotations
import base64, hashlib, io, json, shutil, subprocess, sys, zipfile
from pathlib import Path
WORKING, INPUT = Path("/kaggle/working/neurograph-raw-yelpchi"), Path("/kaggle/input")
ARCHIVE, REVISION = {archive!r}, {revision!r}
def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""): h.update(chunk)
    return h.hexdigest()
WORKING.mkdir(parents=True, exist_ok=True)
PROJECT = WORKING / "project"
with zipfile.ZipFile(io.BytesIO(base64.b64decode(ARCHIVE))) as z: z.extractall(PROJECT)
subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "torch-geometric", "transformers>=4.46,<5"], check=True)
training = sorted(INPUT.rglob("training_data.csv"))
if len(training) != 1: raise RuntimeError("expected one labelled training_data.csv")
raw_graph = WORKING / "raw_graph"
subprocess.run([sys.executable, str(PROJECT / "ml" / "build_yelpchi_raw_graph.py"), "--training-csv", str(training[0]), "--output-dir", str(raw_graph)], check=True, cwd=PROJECT)
subprocess.run([sys.executable, str(PROJECT / "ml" / "train_yelpchi_raw_multimodal.py"), "--raw-graph-dir", str(raw_graph), "--output-root", str(WORKING / "bundles"), "--run-record-dir", str(WORKING / "run-records"), "--roberta-revision", REVISION, "--device", "cuda"], check=True, cwd=PROJECT)
bundle = next((WORKING / "bundles").iterdir()); manifest_sha = sha256(bundle / "run_manifest.json")
subprocess.run([sys.executable, str(PROJECT / "ml" / "reproduce_yelpchi_multimodal_bundle.py"), "--bundle-dir", str(bundle), "--manifest-sha256", manifest_sha], check=True, cwd=PROJECT)
out = Path("/kaggle/working/neurograph-raw-yelpchi-output")
if out.exists(): shutil.rmtree(out)
out.mkdir(); shutil.copytree(bundle, out / "bundle"); shutil.copytree(WORKING / "run-records", out / "run-records"); shutil.copy2(raw_graph / "graph_manifest.json", out / "raw_graph_manifest.json")
print(json.dumps({{"status":"passed", "output":str(out), "manifest_sha256":manifest_sha}}, indent=2))
'''


def project_archive() -> str:
    files = ["build_yelpchi_raw_graph.py", "train_yelpchi_raw_multimodal.py", "train_yelpchi_multimodal.py", "reproduce_yelpchi_multimodal_bundle.py"]
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in files: archive.write(ML / file, f"ml/{file}")
        archive.write(ML / "models" / "roberta_relation_gnn.py", "ml/models/roberta_relation_gnn.py")
    return base64.b64encode(content.getvalue()).decode()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kaggle-username", required=True)
    parser.add_argument("--text-dataset-ref", default="samygithub/collective-opinion-spam-detection")
    parser.add_argument("--roberta-revision", required=True)
    parser.add_argument("--kernel-slug", default="neurograph-raw-yelpchi-multimodal-gnn")
    parser.add_argument("--output-dir", default=".kaggle/neurograph-raw-yelpchi-multimodal")
    args = parser.parse_args()
    if "/" not in args.text_dataset_ref: raise ValueError("--text-dataset-ref needs owner/dataset-slug")
    out = Path(args.output_dir).resolve()
    if out.exists(): shutil.rmtree(out)
    out.mkdir(parents=True)
    metadata = {"id": f"{args.kaggle_username}/{args.kernel_slug}", "title": "NeuroGraph Raw YelpChi Multimodal GNN", "code_file": "run_raw_yelpchi.py", "language": "python", "kernel_type": "script", "is_private": "true", "enable_gpu": "true", "enable_internet": "true", "machine_shape": "NvidiaTeslaT4", "dataset_sources": [args.text_dataset_ref], "competition_sources": [], "kernel_sources": [], "model_sources": []}
    (out / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (out / "run_raw_yelpchi.py").write_text(RUNNER.format(archive=project_archive(), revision=args.roberta_revision))
    print(json.dumps({"kernel_dir": str(out), "kernel_id": metadata["id"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
