#!/bin/bash
set -euo pipefail

exec 9>/opt/neurograph/deployment.lock
flock -n 9 || { echo 'A deployment is already running'; exit 1; }

cd /opt/neurograph
chmod 600 .env
set -a
source .env
set +a
compose=(docker compose --env-file /opt/neurograph/.env -f /opt/neurograph/source/deploy/aws/compose.yaml)

echo 'Starting PostgreSQL and Neo4j'
"${compose[@]}" up -d --wait --wait-timeout 600 postgres neo4j
echo 'Building the CPU backend image'
"${compose[@]}" build backend

if [ ! -f /opt/neurograph/database-imported ]; then
    echo 'Importing the working demo database'
    "${compose[@]}" exec -T postgres pg_restore --single-transaction --exit-on-error \
        --no-owner --no-privileges -U neurograph -d neurograph < bootstrap/database.dump
    touch /opt/neurograph/database-imported
fi

"${compose[@]}" run --rm backend alembic upgrade head
"${compose[@]}" run --rm -e ADMIN_PASSWORD -e FACULTY_PASSWORD backend python scripts/setup_deployment_users.py
"${compose[@]}" run --rm backend python scripts/project_synthetic_campaign.py

echo 'Checking the verified models and caching the pinned text encoder'
"${compose[@]}" run --rm backend python -u -c '
from app.services.yelpchi_baseline import VerifiedYelpChiBaseline
from app.services.yelpchi_multimodal import VerifiedYelpChiMultimodal
from app.services.inductive_yelpchi import InductiveYelpChiRuntime
baseline = VerifiedYelpChiBaseline()
baseline._load()
print("Verified baseline loaded", flush=True)
status = VerifiedYelpChiMultimodal().status()
assert status["available"], status["details"]
print("Verified multimodal reproduction passed", flush=True)
runtime = InductiveYelpChiRuntime()
runtime.verify_and_load()
assert runtime.encode_texts(["The service was friendly and the food was good."], batch_size=1).shape == (1, 768)
print("Verified inductive reproduction and pinned text encoder passed", flush=True)
'

echo 'Starting the HTTPS API'
"${compose[@]}" up -d --wait --wait-timeout 300 backend caddy
"${compose[@]}" ps
echo 'Backend deployment completed'
