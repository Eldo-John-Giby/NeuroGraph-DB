"""
Ingestion script for YelpChi dataset into PostgreSQL and local storage.
Creates tables from sql/01_schema.sql, assigns node_idx 0..N-1, and inserts users, products, and reviews.
"""

import os
import argparse
import pandas as pd
import numpy as np

DEFAULT_DB_URL = "postgresql://neuro:neuro@localhost:5432/neurograph"


def ingest_data(db_url: str | None = None, raw_csv_path: str | None = None) -> pd.DataFrame:
    raw_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "raw"))
    if raw_csv_path is None:
        raw_csv_path = os.path.join(raw_dir, "yelpchi_reviews.csv")

    if not os.path.exists(raw_csv_path):
        import importlib
        get_data_mod = importlib.import_module("data_pipeline.scripts.01_get_data")
        get_data_mod.generate_standard_yelpchi()


    df = pd.read_csv(raw_csv_path)
    # Ensure node_idx 0..N-1
    df["node_idx"] = np.arange(len(df), dtype=int)
    if "split" not in df.columns:
        df["split"] = None

    # Save processed intermediate
    processed_path = os.path.join(raw_dir, "processed_reviews.parquet")
    df.to_parquet(processed_path, index=False)
    print(f"Saved processed reviews to {processed_path}")

    # If Postgres connection is available, ingest into Postgres
    if db_url is None:
        db_url = os.environ.get("DATABASE_URL", DEFAULT_DB_URL)

    try:
        import psycopg2
        from psycopg2.extras import execute_values

        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        # Run schema and indexes
        schema_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sql", "01_schema.sql"))
        if os.path.exists(schema_path):
            with open(schema_path, "r") as f:
                cur.execute(f.read())

        # Ingest users
        unique_users = [(u,) for u in df["user_id"].unique()]
        execute_values(cur, "INSERT INTO users (user_id) VALUES %s ON CONFLICT (user_id) DO NOTHING;", unique_users)

        # Ingest products
        unique_prods = [(p,) for p in df["prod_id"].unique()]
        execute_values(cur, "INSERT INTO products (prod_id) VALUES %s ON CONFLICT (prod_id) DO NOTHING;", unique_prods)

        # Ingest reviews
        review_records = [
            (
                row["review_id"],
                int(row["node_idx"]),
                row["user_id"],
                row["prod_id"],
                int(row["rating"]),
                row["review_date"],
                row["review_text"],
                int(row["label"]),
                row.get("split")
            )
            for _, row in df.iterrows()
        ]
        review_query = """
        INSERT INTO reviews (review_id, node_idx, user_id, prod_id, rating, review_date, review_text, label, split)
        VALUES %s
        ON CONFLICT (review_id) DO UPDATE SET
            node_idx = EXCLUDED.node_idx,
            rating = EXCLUDED.rating,
            label = EXCLUDED.label;
        """
        execute_values(cur, review_query, review_records, page_size=2000)
        conn.commit()
        cur.close()
        conn.close()
        print(f"Successfully ingested {len(review_records)} reviews into PostgreSQL database.")
    except Exception as e:
        print(f"PostgreSQL ingestion skipped or unavailable ({e}). Data saved to local parquet.")

    return df


def main():
    parser = argparse.ArgumentParser(description="Ingest YelpChi data")
    parser.add_argument("--db-url", type=str, default=None)
    parser.add_argument("--csv-path", type=str, default=None)
    args = parser.parse_args()

    ingest_data(db_url=args.db_url, raw_csv_path=args.csv_path)


if __name__ == "__main__":
    main()