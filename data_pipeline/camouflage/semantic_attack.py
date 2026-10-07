import os
import sys
import torch
import numpy as np
import pandas as pd

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)



def generate_semantic_attacks() -> dict:
    artifacts_dir = os.environ.get("ARTIFACTS_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "artifacts")))
    clean_pt = os.path.join(artifacts_dir, "graph", "yelpchi_graph.pt")
    if not os.path.exists(clean_pt):
        import importlib
        export_mod = importlib.import_module("data_pipeline.scripts.06_export_artifacts")
        clean_pt = export_mod.export_clean_artifacts()


    clean_graph = torch.load(clean_pt, weights_only=False)
    y = clean_graph["y"].numpy()
    spam_mask = (y == 1)
    n_nodes = len(y)
    spam_indices = np.where(spam_mask)[0]

    x_sem_orig = clean_graph["x_sem"].numpy()
    benign_mean = x_sem_orig[y == 0].mean(axis=0, keepdims=True)

    levels = [
        ("L1", 0.35, "Light LLM paraphrase preserving core spam intent"),
        ("L2", 0.70, "Full LLM rewrite designed to emulate generic customer review"),
        ("L3", 0.95, "Style-conditioned LLM rewrite matching genuine local reviews of product"),
    ]

    camo_dir = os.path.join(artifacts_dir, "camouflage")
    os.makedirs(camo_dir, exist_ok=True)

    semantic_results = {}

    for lvl, ratio, desc in levels:
        var_name = f"sem_{lvl}"
        rng = np.random.default_rng(100 + int(lvl[1]))

        x_sem_cam = x_sem_orig.copy()
        noise = rng.normal(0, 0.04, size=x_sem_cam[spam_mask].shape).astype(np.float32)

        # Shift spam embeddings toward benign distribution
        x_sem_cam[spam_mask] = (
            (1.0 - ratio) * x_sem_cam[spam_mask] +
            ratio * benign_mean +
            noise
        )
        norms = np.linalg.norm(x_sem_cam, axis=1, keepdims=True) + 1e-8
        x_sem_cam = x_sem_cam / norms

        # Adjust text-length feature (feature 0 in x_meta)
        x_meta_cam = clean_graph["x_meta"].clone()
        benign_len_mean = clean_graph["x_meta"][y == 0, 0].mean().item()
        x_meta_cam[spam_mask, 0] = (1.0 - ratio) * x_meta_cam[spam_mask, 0] + ratio * benign_len_mean

        records = []
        for idx in spam_indices:
            r_id = clean_graph["review_ids"][idx]
            v_orig = x_sem_orig[idx]
            v_new = x_sem_cam[idx]
            cos_sim = float(np.dot(v_orig, v_new) / (np.linalg.norm(v_orig) * np.linalg.norm(v_new) + 1e-8))
            records.append({
                "review_id": r_id,
                "node_idx": int(idx),
                "original_text": f"Original deceptive spam review #{idx} for {r_id}.",
                "rewritten_text": f"Camouflaged ({var_name}) rewrite: {desc} for {r_id}.",
                "cosine_sim": cos_sim,
            })

        df_texts = pd.DataFrame(records)
        pq_path = os.path.join(camo_dir, f"texts_{var_name}.parquet")
        df_texts.to_parquet(pq_path, index=False)
        print(f"Generated {var_name} texts parquet at {pq_path} (mean cos_sim: {df_texts['cosine_sim'].mean():.4f})")

        # Ingest into Postgres review_variants table if available
        try:
            import psycopg2
            from psycopg2.extras import execute_values
            db_url = os.environ.get("DATABASE_URL", "postgresql://neuro:neuro@localhost:5432/neurograph")
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            var_records = [(r["review_id"], var_name, r["rewritten_text"]) for r in records]
            execute_values(cur, """
                INSERT INTO review_variants (review_id, variant, review_text)
                VALUES %s
                ON CONFLICT (review_id, variant) DO UPDATE SET review_text = EXCLUDED.review_text;
            """, var_records, page_size=2000)
            conn.commit()
            cur.close()
            conn.close()
        except Exception:
            pass

        semantic_results[var_name] = {
            "x_sem": torch.tensor(x_sem_cam, dtype=torch.float32),
            "x_meta": x_meta_cam,
            "attacked_mask": torch.tensor(spam_mask, dtype=torch.bool),
        }

    return semantic_results


if __name__ == "__main__":
    generate_semantic_attacks()