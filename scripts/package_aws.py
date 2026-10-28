#!/usr/bin/env python3
"""Package active sources, verified bundles, and a database export for private upload."""

import argparse
import hashlib
import json
from pathlib import Path
import secrets
import tarfile


ROOT = Path(__file__).resolve().parents[1]
BUNDLES = (
    "artifacts/verified_baselines/kaggle_output/neurograph-yelpchi-output/bundle",
    "artifacts/verified_multimodal/raw_yelpchi_multimodal_seed42_20261025T071547Z",
    "artifacts/verified_inductive/raw_yelpchi_inductive_seed42_20261025T125837Z",
)


def source_filter(member):
    parts = Path(member.name).parts
    excluded = {".git", "node_modules", ".next", ".vercel", "__pycache__", ".pytest_cache", ".venv"}
    if any(part in excluded or part.startswith(".env") for part in parts):
        return None
    if member.name.startswith(("source/backend/data", "source/backend/tests")):
        return None
    if member.name.endswith((".pyc", ".DS_Store")):
        return None
    return member


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument("--database-dump", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    state = json.loads(args.state_file.read_text())
    if not args.database_dump.is_file() or args.database_dump.stat().st_size == 0:
        raise SystemExit("A completed PostgreSQL export is required")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.output_dir.chmod(0o700)
    credentials_path = args.output_dir / "deployment-credentials.json"
    if credentials_path.exists():
        credentials = json.loads(credentials_path.read_text())
    else:
        credentials = {
            "admin_email": "admin@neurograph.local", "admin_password": secrets.token_urlsafe(24),
            "faculty_email": "faculty@neurograph.demo", "faculty_password": secrets.token_urlsafe(24),
            "postgres_password": secrets.token_hex(24), "neo4j_password": secrets.token_hex(24),
            "jwt_secret_key": secrets.token_hex(48),
        }
        credentials_path.write_text(json.dumps(credentials, indent=2) + "\n")
        credentials_path.chmod(0o600)
    production_env = args.output_dir / "production.env"
    production_env.write_text("\n".join((
        "POSTGRES_PASSWORD=" + credentials["postgres_password"],
        "NEO4J_PASSWORD=" + credentials["neo4j_password"],
        "JWT_SECRET_KEY=" + credentials["jwt_secret_key"],
        "ADMIN_PASSWORD=" + credentials["admin_password"],
        "FACULTY_PASSWORD=" + credentials["faculty_password"],
        "BACKEND_DOMAIN=" + state["backend_domain"],
    )) + "\n")
    production_env.chmod(0o600)
    target = args.output_dir / "deployment.tar.gz"
    with tarfile.open(target, "w:gz", compresslevel=3) as archive:
        for name in ("backend", "ml", "docs/runs", "deploy/aws", ".dockerignore"):
            archive.add(ROOT / name, arcname="source/" + name, filter=source_filter)
        for name in BUNDLES:
            if not (ROOT / name / "run_manifest.json").is_file():
                raise SystemExit("Verified bundle is missing: " + name)
            archive.add(ROOT / name, arcname=name)
        archive.add(args.database_dump, arcname="bootstrap/database.dump")
        archive.add(production_env, arcname=".env")
    target.chmod(0o600)
    digest = hashlib.file_digest(target.open("rb"), "sha256").hexdigest()
    metadata = {"archive": str(target.resolve()), "sha256": digest, "bytes": target.stat().st_size}
    (args.output_dir / "package.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
