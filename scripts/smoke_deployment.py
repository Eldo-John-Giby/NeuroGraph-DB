#!/usr/bin/env python3
"""Verify public authentication, model serving, CSV scoring, and Neo4j projection."""

import argparse
import csv
import http.cookiejar
import io
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origin")
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--score-csv", action="store_true")
    args = parser.parse_args()
    credentials = json.loads(args.credentials.read_text())
    origin = args.origin.rstrip("/")
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    token = None

    def request(path, data=None, method=None, content_type="application/json"):
        headers = {}
        if token:
            headers["Authorization"] = "Bearer " + token
        if data is not None:
            headers["Content-Type"] = content_type
            if not isinstance(data, bytes):
                data = json.dumps(data).encode()
        started = time.monotonic()
        try:
            response = client.open(urllib.request.Request(origin + path, data=data, headers=headers, method=method), timeout=600)
            with response:
                result = json.load(response)
        except urllib.error.HTTPError as exc:
            raise SystemExit(f"{path} returned HTTP {exc.code}: {exc.read().decode()}") from exc
        print(f"PASS {method or ('POST' if data is not None else 'GET')} {path} ({time.monotonic()-started:.1f}s)", flush=True)
        return result

    assert request("/health/live")["status"] == "alive"
    result = request("/api/v1/auth/login", {"email": credentials["faculty_email"], "password": credentials["faculty_password"]})
    token = result["access_token"]
    assert request("/api/v1/auth/me")["role_key"] == "RESEARCHER"
    result = request("/api/v1/auth/refresh", {})
    token = result["access_token"]
    for model in ("verified-baseline", "verified-multimodal"):
        assert request(f"/api/v1/{model}/status")["available"]
        result = request(f"/api/v1/{model}/results?limit=2")
        assert result["items"]
    request("/api/v1/reviews?limit=2")
    request("/api/v1/products?limit=2")
    graph = request("/api/v1/synthetic-campaigns/harbor-table-review-bombing-seed-42/graph")
    assert graph["nodes"]
    snapshots = request("/api/v1/graph-snapshots")["items"]
    if not args.score_csv:
        return
    snapshot = next(item for item in snapshots if item["batch_context_permitted"] and
                    item["context_scope_key"] == "inductive-rur-rsr-rtr-v1")
    run_key = uuid.uuid4().hex[:12]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["review_id", "reviewer_id", "product_id", "rating", "review_date", "review_text"])
    for index, text in enumerate(("Friendly service and tasty food. I would visit this restaurant again.",
                                  "The food arrived cold and the staff were unhelpful during my visit.",
                                  "The meal was pleasant and the restaurant was clean and welcoming.")):
        writer.writerow([f"deploy-{run_key}-{index}", f"deploy-reviewer-{run_key}-{index}",
                         f"deploy-product-{run_key}", [5, 1, 4][index], f"2026-10-{20+index}", text])
    boundary = "NeuroGraphBoundary" + uuid.uuid4().hex
    parts = []
    for name, value in {"source_system": "deployment-smoke", "historic_graph_snapshot_id": str(snapshot["graph_snapshot_id"])}.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="deployment-check.csv"\r\nContent-Type: text/csv\r\n\r\n'.encode() + buffer.getvalue().encode() + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    batch = request("/api/v1/batch-analyses", b"".join(parts), content_type="multipart/form-data; boundary=" + boundary)
    assert batch["accepted_count"] == 3, batch
    batch_id = batch["batch_analysis_id"]
    batch = request(f"/api/v1/batch-analyses/{batch_id}/score", b"", content_type="application/x-www-form-urlencoded")
    assert batch["status"] == "completed", batch
    rows = request(f"/api/v1/batch-analyses/{batch_id}/results")
    assert len(rows["items"]) == 3 and all(row["prediction"] for row in rows["items"])
    graph = request(f"/api/v1/batch-analyses/{batch_id}/graph", {})
    assert graph["nodes"] and graph["source"] == "neo4j_upload_analysis"
    print(json.dumps({"batch_analysis_id": batch_id, "scored_reviews": 3,
                      "graph_nodes": len(graph["nodes"]), "graph_relationships": len(graph["relationships"])}))


if __name__ == "__main__":
    main()
