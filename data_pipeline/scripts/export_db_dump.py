"""
Database Export Dump Utility for NeuroGraph-DB.
Generates a complete standalone SQL database dump (DDL + DML) in artifacts/db_dump/neurograph.sql
and artifacts/db_dump/neurograph.sql.gz.
Works via pg_dump if PostgreSQL is active, or builds an offline SQL dump
from processed_reviews.parquet, review_variants, and model predictions.
"""

import os
import sys
import glob
import gzip
import pandas as pd

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


def sql_escape(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "NULL"
    if isinstance(val, (int, float)):
        return str(val)
    # escape single quotes
    clean = str(val).replace("'", "''")
    return f"'{clean}'"


def generate_sql_dump(output_sql_path: str, db_url: str | None = None):
    out_dir = os.path.dirname(output_sql_path)
    os.makedirs(out_dir, exist_ok=True)

    # 1. Try pg_dump if postgres is reachable
    if db_url is None:
        db_url = os.environ.get("DATABASE_URL", "postgresql://neuro:neuro@localhost:5432/neurograph")

    # Check if we can dump live postgres
    try:
        import subprocess
        print(f"Attempting pg_dump from {db_url}...")
        result = subprocess.run(
            ["pg_dump", db_url, "-f", output_sql_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )
        if result.returncode == 0 and os.path.exists(output_sql_path) and os.path.getsize(output_sql_path) > 0:
            print(f"Live pg_dump completed successfully to {output_sql_path}")
            compress_dump(output_sql_path)
            return
    except Exception as e:
        print(f"pg_dump skipped or unavailable ({e}). Generating standalone SQL dump from pipeline artifacts...")

    # 2. Standalone generator from artifacts
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    schema_path = os.path.join(data_dir, "sql", "01_schema.sql")
    indexes_path = os.path.join(data_dir, "sql", "02_indexes.sql")
    reviews_parquet = os.path.join(data_dir, "raw", "processed_reviews.parquet")

    if not os.path.exists(reviews_parquet):
        raise FileNotFoundError(f"Missing {reviews_parquet}")

    df = pd.read_parquet(reviews_parquet)

    with open(output_sql_path, "w", encoding="utf-8") as f:
        f.write("-- ==================================================================\n")
        f.write("-- NeuroGraph-DB Complete Database Dump (YelpChi 5,000 Dataset)\n")
        f.write("-- Tables: users, products, reviews, review_variants, fraud_predictions\n")
        f.write("-- ==================================================================\n\n")

        # Write schema
        if os.path.exists(schema_path):
            with open(schema_path, "r", encoding="utf-8") as sf:
                f.write(sf.read())
            f.write("\n\n")

        # Ingest users
        f.write("-- --- USERS ---\n")
        users = df["user_id"].unique()
        f.write("INSERT INTO users (user_id) VALUES\n")
        user_vals = [f"({sql_escape(u)})" for u in users]
        f.write(",\n".join(user_vals))
        f.write("\nON CONFLICT (user_id) DO NOTHING;\n\n")

        # Ingest products
        f.write("-- --- PRODUCTS ---\n")
        prods = df["prod_id"].unique()
        f.write("INSERT INTO products (prod_id) VALUES\n")
        prod_vals = [f"({sql_escape(p)})" for p in prods]
        f.write(",\n".join(prod_vals))
        f.write("\nON CONFLICT (prod_id) DO NOTHING;\n\n")

        # Ingest reviews (in batches of 500)
        f.write("-- --- REVIEWS ---\n")
        batch_size = 500
        for i in range(0, len(df), batch_size):
            chunk = df.iloc[i : i + batch_size]
            f.write("INSERT INTO reviews (review_id, node_idx, user_id, prod_id, rating, review_date, review_text, label, split) VALUES\n")
            row_vals = []
            for _, row in chunk.iterrows():
                row_str = f"({sql_escape(row['review_id'])}, {int(row['node_idx'])}, {sql_escape(row['user_id'])}, {sql_escape(row['prod_id'])}, {int(row['rating'])}, {sql_escape(row['review_date'])}, {sql_escape(row['review_text'])}, {int(row['label'])}, {sql_escape(row.get('split'))})"
                row_vals.append(row_str)
            f.write(",\n".join(row_vals))
            f.write("\nON CONFLICT (review_id) DO NOTHING;\n\n")

        # Ingest review variants if available
        camo_dir = os.path.join(_repo_root, "artifacts", "camouflage")
        variant_files = glob.glob(os.path.join(camo_dir, "texts_sem_L*.parquet"))
        if variant_files:
            f.write("-- --- REVIEW VARIANTS (SEMANTIC CAMOUFLAGE) ---\n")
            for vf in variant_files:
                var_name = os.path.splitext(os.path.basename(vf))[0].replace("texts_", "")
                vdf = pd.read_parquet(vf)
                if not vdf.empty:
                    f.write(f"-- Variant: {var_name}\n")
                    f.write("INSERT INTO review_variants (review_id, variant, review_text) VALUES\n")
                    v_vals = [f"({sql_escape(r['review_id'])}, {sql_escape(var_name)}, {sql_escape(r.get('rewritten_text', r.get('review_text')))})" for _, r in vdf.iterrows()]
                    f.write(",\n".join(v_vals))
                    f.write("\nON CONFLICT (review_id, variant) DO NOTHING;\n\n")

        # Ingest predictions if available
        pred_dir = os.path.join(_repo_root, "artifacts", "predictions")
        pred_files = sorted(glob.glob(os.path.join(pred_dir, "neurograph_clean_clean_*.parquet")))
        if pred_files:
            latest_pred = pred_files[-1]
            pdf = pd.read_parquet(latest_pred)
            run_id = os.path.splitext(os.path.basename(latest_pred))[0]
            f.write(f"-- --- FRAUD PREDICTIONS ({run_id}) ---\n")
            for i in range(0, len(pdf), batch_size):
                p_chunk = pdf.iloc[i : i + batch_size]
                f.write("INSERT INTO fraud_predictions (review_id, run_id, model_name, variant, fraud_score, predicted_label) VALUES\n")
                p_vals = [
                    f"({sql_escape(r['review_id'])}, {sql_escape(run_id)}, 'neurograph', {sql_escape(r.get('variant', 'clean'))}, {float(r['fraud_score'])}, {int(r['predicted_label'])})"
                    for _, r in p_chunk.iterrows()
                ]
                f.write(",\n".join(p_vals))
                f.write("\nON CONFLICT (review_id, run_id) DO NOTHING;\n\n")

        # Write indexes
        if os.path.exists(indexes_path):
            f.write("-- --- INDEXES ---\n")
            with open(indexes_path, "r", encoding="utf-8") as inf:
                f.write(inf.read())
            f.write("\n")

    print(f"Generated complete SQL dump at {output_sql_path} ({os.path.getsize(output_sql_path) / 1024:.1f} KB)")
    compress_dump(output_sql_path)


def compress_dump(sql_path: str):
    gz_path = f"{sql_path}.gz"
    with open(sql_path, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
        f_out.writelines(f_in)
    print(f"Compressed SQL dump to {gz_path} ({os.path.getsize(gz_path) / 1024:.1f} KB)")


if __name__ == "__main__":
    out_path = os.path.join(_repo_root, "artifacts", "db_dump", "neurograph.sql")
    generate_sql_dump(out_path)
