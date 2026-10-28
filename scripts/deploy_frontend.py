#!/usr/bin/env python3
"""Build and deploy the frontend after its backend is publicly reachable."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import urllib.error
import urllib.request
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "db-dashboard/frontend"
VERCEL = ["npx", "--yes", "vercel@65.5.0"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backend_url", nargs="?", default=os.environ.get("BACKEND_URL"))
    args = parser.parse_args()
    backend_url = (args.backend_url or "").rstrip("/")
    parsed = urlsplit(backend_url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.path
            or parsed.query or parsed.fragment or parsed.username or parsed.password):
        parser.error("Provide the backend HTTPS origin, e.g. https://api.example.org")

    try:
        with urllib.request.urlopen(backend_url + "/health/live", timeout=60) as response:
            if json.load(response).get("status") != "alive":
                raise ValueError("unexpected backend health response")
    except (urllib.error.URLError, ValueError) as exc:
        raise SystemExit(f"Backend health check failed: {exc}") from exc

    deployment_env = {**os.environ, "BACKEND_URL": backend_url}

    def vercel(*arguments, input_value=None):
        subprocess.run(
            [*VERCEL, *arguments], cwd=FRONTEND, env=deployment_env,
            input=input_value, text=True, check=True,
        )

    if not (FRONTEND / ".vercel/project.json").exists():
        vercel("link", "--yes")

    # Only the frontend's proxy target belongs here. Database passwords, JWT
    # secrets, and Vercel's generated OIDC token stay out of the frontend env.
    vercel("env", "add", "BACKEND_URL", "--environment", "production",
           "--type", "config", "--force", "--yes", input_value=backend_url + "\n")
    vercel("pull", "--yes", "--environment=production")
    vercel("build", "--prod")
    vercel("deploy", "--prebuilt", "--prod", "--yes")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc
