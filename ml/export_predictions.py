"""
Export Predictions Module for NeuroGraph-DB.
Saves predictions to artifacts/predictions/<run_id>.parquet and optionally upserts
into PostgreSQL table fraud_predictions using psycopg2.extras.execute_values.
"""

import os
import sys
import argparse
import pandas as pd

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from ml.data import get_artifacts_dir

DEFAULT_DB_URL = "postgresql://neuro:neuro@localhost:5432/neurograph"


def export_run_to_postgres(
    run_id: str,
    db_url: str | None = None,
    artifacts_dir: str | None = None,
    batch_size: int = 2000
) -> int:
    """
    Reads artifacts/predictions/<run_id>.parquet and upserts into Postgres fraud_predictions table.
    """
    import psycopg2
    from psycopg2.extras import execute_values

    if artifacts_dir is None:
        artifacts_dir = get_artifacts_dir()
    if db_url is None:
        db_url = os.environ.get("DATABASE_URL", DEFAULT_DB_URL)

    pq_path = os.path.join(artifacts_dir, "predictions", f"{run_id}.parquet")
    if not os.path.exists(pq_path):
        raise FileNotFoundError(f"Prediction parquet not found at {pq_path}")

    df = pd.read_parquet(pq_path)
    model_name = run_id.split("_")[0]

    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()

    # Ensure table exists if DB initialized
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fraud_predictions (
        review_id TEXT,
        run_id TEXT,
        model_name TEXT,
        variant TEXT NOT NULL DEFAULT 'clean',
        fraud_score REAL,
        predicted_label SMALLINT,
        created_at TIMESTAMPTZ DEFAULT now(),
        PRIMARY KEY(review_id, run_id)
    );
    """)

    query = """
    INSERT INTO fraud_predictions (review_id, run_id, model_name, variant, fraud_score, predicted_label)
    VALUES %s
    ON CONFLICT (review_id, run_id) DO UPDATE SET
        fraud_score = EXCLUDED.fraud_score,
        predicted_label = EXCLUDED.predicted_label,
        model_name = EXCLUDED.model_name,
        variant = EXCLUDED.variant;
    """

    records = [
        (
            str(row["review_id"]),
            run_id,
            model_name,
            str(row.get("variant", "clean")),
            float(row["fraud_score"]),
            int(row["predicted_label"]),
        )
        for _, row in df.iterrows()
    ]

    execute_values(cursor, query, records, page_size=batch_size)
    conn.commit()
    count = len(records)
    cursor.close()
    conn.close()
    print(f"Successfully upserted {count} prediction records into Postgres table fraud_predictions.")
    return count


def main():
    parser = argparse.ArgumentParser(description="Export prediction parquets to PostgreSQL")
    parser.add_argument("--run-id", type=str, required=True, help="Run ID of predictions to export")
    parser.add_argument("--db-url", type=str, default=None, help="PostgreSQL connection URI")
    parser.add_argument("--artifacts-dir", type=str, default=None)
    args = parser.parse_args()

    export_run_to_postgres(args.run_id, db_url=args.db_url, artifacts_dir=args.artifacts_dir)


if __name__ == "__main__":
    main()
