"""One-shot worker for projecting a synthetic_demo campaign to Neo4j."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import make_session_factory
from app.services.neo4j_synthetic_projection import project_synthetic_campaign


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-key", default="harbor-table-review-bombing-seed-42")
    args = parser.parse_args()
    session_factory = make_session_factory()
    try:
        with session_factory() as db:
            result = project_synthetic_campaign(db, args.campaign_key)
    except LookupError as exc:
        raise SystemExit(f"Cannot project campaign: {exc} Seed it first with DEMO_MODE=true and scripts/seed_demo_batch.py.") from None
    print(json.dumps(result, sort_keys=True))
    print("Projection contains synthetic_demo PostgreSQL scenario records; it is not model inference.")


if __name__ == "__main__":
    main()
