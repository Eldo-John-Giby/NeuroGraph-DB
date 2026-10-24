#!/usr/bin/env python3
"""Create a private Kaggle GPU kernel package for the verified GNN baseline.

The generated package contains only the training code.  The selected Kaggle
dataset remains an attached Kaggle input; raw data and trained weights are not
added to this Git repository.
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

import base64
import hashlib
import io
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

KAGGLE_DATASET_REF = {dataset_ref!r}
PROJECT_ARCHIVE_B64 = {project_archive_b64!r}
EXPECTED_YELPCHI_SHA256 = "fedb35a8fa539b27866244d3515a47a76b20080cdacb33112da3458fd2487b42"
WORKING = Path("/kaggle/working/neurograph-yelpchi")
PROJECT = WORKING / "project"
INPUT = Path("/kaggle/input")

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

try:
    import torch_geometric  # noqa: F401
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "torch-geometric"], check=True)

mat_files = sorted(INPUT.rglob("YelpChi.mat"))
if not mat_files:
    archives = sorted(INPUT.rglob("*.zip"))
    matching_archives = []
    for archive in archives:
        with zipfile.ZipFile(archive) as handle:
            if any(Path(name).name == "YelpChi.mat" for name in handle.namelist()):
                matching_archives.append(archive)
    if len(matching_archives) == 1:
        with zipfile.ZipFile(matching_archives[0]) as handle:
            member = next(name for name in handle.namelist() if Path(name).name == "YelpChi.mat")
            handle.extract(member, WORKING)
        mat_files = sorted(WORKING.rglob("YelpChi.mat"))
if len(mat_files) != 1:
    raise RuntimeError("Expected one attached YelpChi.mat; found: " + ", ".join(map(str, mat_files)))
mat_path = mat_files[0]
if sha256(mat_path) != EXPECTED_YELPCHI_SHA256:
    raise RuntimeError("Attached YelpChi.mat does not match the trusted structured benchmark SHA256")
WORKING.mkdir(parents=True, exist_ok=True)
if not (PROJECT / "ml" / "inspect_yelpchi.py").exists():
    PROJECT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(PROJECT_ARCHIVE_B64))) as archive:
        archive.extractall(PROJECT)
evidence = WORKING / "acquisition.json"
evidence.write_text(json.dumps({{
    "schema_version": 1,
    "dataset_ref": KAGGLE_DATASET_REF,
    "source_url": "https://www.kaggle.com/datasets/" + KAGGLE_DATASET_REF,
    "dataset_file": mat_path.name,
    "dataset_sha256": sha256(mat_path),
    "execution": "attached_kaggle_input",
}}, indent=2) + "\\n")
inspection = WORKING / "inspection.json"
subprocess.run([sys.executable, str(PROJECT / "ml" / "inspect_yelpchi.py"), "--mat-path", str(mat_path), "--output", str(inspection)], check=True, cwd=PROJECT)
report = json.loads(inspection.read_text())
if report["selected_pipeline"] != "structured_32_feature_gnn":
    raise RuntimeError("Refusing to train: " + report["selection_reason"])
subprocess.run([
    sys.executable, str(PROJECT / "ml" / "train_yelpchi_gnn_baseline.py"),
    "--mat-path", str(mat_path),
    "--source-evidence", str(evidence),
    "--output-root", str(WORKING / "bundles"),
    "--run-record-dir", str(WORKING / "run-records"),
    "--device", "cuda", "--epochs", "100", "--patience", "15", "--hidden-dim", "64",
], check=True, cwd=PROJECT)
bundle = next((WORKING / "bundles").iterdir())
manifest = bundle / "run_manifest.json"
manifest_hash = sha256(manifest)
subprocess.run([
    sys.executable, str(PROJECT / "ml" / "reproduce_yelpchi_gnn_bundle.py"),
    "--bundle-dir", str(bundle), "--manifest-sha256", manifest_hash,
], check=True, cwd=PROJECT)
output = Path("/kaggle/working/neurograph-yelpchi-output")
if output.exists():
    shutil.rmtree(output)
output.mkdir(parents=True, exist_ok=True)
shutil.copytree(bundle, output / "bundle")
shutil.copy2(inspection, output / "inspection.json")
shutil.copy2(evidence, output / "acquisition.json")
shutil.copytree(WORKING / "run-records", output / "run-records")
print(json.dumps({{"status": "passed", "output": str(output), "manifest_sha256": manifest_hash}}, indent=2))
'''


def copy_project(destination: Path) -> None:
    (destination / "ml" / "models").mkdir(parents=True)
    for name in (
        "inspect_yelpchi.py",
        "train_yelpchi_gnn_baseline.py",
        "reproduce_yelpchi_gnn_bundle.py",
    ):
        shutil.copy2(ML_ROOT / name, destination / "ml" / name)
    for source in (ML_ROOT / "models").glob("*.py"):
        shutil.copy2(source, destination / "ml" / "models" / source.name)


def build_project_archive() -> str:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in (
            "inspect_yelpchi.py",
            "train_yelpchi_gnn_baseline.py",
            "reproduce_yelpchi_gnn_bundle.py",
        ):
            archive.write(ML_ROOT / name, arcname=f"ml/{name}")
        for source in sorted((ML_ROOT / "models").glob("*.py")):
            archive.write(source, arcname=f"ml/models/{source.name}")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kaggle-username", required=True)
    parser.add_argument("--dataset-ref", required=True, help="Kaggle owner/dataset-slug verified by the caller")
    parser.add_argument("--kernel-slug", default="neurograph-yelpchi-gnn-baseline")
    parser.add_argument("--output-dir", default=".kaggle/neurograph-yelpchi-gnn-baseline")
    args = parser.parse_args()
    if "/" not in args.dataset_ref or "/" in args.kaggle_username:
        raise ValueError("Use owner/dataset-slug for --dataset-ref and a bare account slug for --kaggle-username")
    output = Path(args.output_dir).resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    copy_project(output / "project")
    metadata = {
        "id": f"{args.kaggle_username}/{args.kernel_slug}",
        "title": "NeuroGraph YelpChi GNN Baseline",
        "code_file": "run_yelpchi_baseline.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": "true",
        "enable_gpu": "true",
        "enable_internet": "true",
        "machine_shape": "NvidiaTeslaT4",
        "dataset_sources": [args.dataset_ref],
        "competition_sources": [],
        "kernel_sources": [],
        "model_sources": [],
    }
    (output / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (output / "run_yelpchi_baseline.py").write_text(
        RUNNER.format(
            dataset_ref=args.dataset_ref,
            project_archive_b64=build_project_archive(),
        )
    )
    print(json.dumps({"kernel_dir": str(output), "kernel_id": metadata["id"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
