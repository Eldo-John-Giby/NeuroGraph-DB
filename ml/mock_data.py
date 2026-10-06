"""
Generate synthetic mock YelpChi graph and camouflage variants for NeuroGraph-DB.
Complies strictly with the ARTIFACT CONTRACT.
"""

import os
import argparse
import numpy as np
import torch
import pandas as pd


def get_artifacts_dir() -> str:
    default_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "artifacts"))
    return os.environ.get("ARTIFACTS_DIR", default_dir)


def make_undirected(edge_index: torch.Tensor) -> torch.Tensor:
    """Ensure edge_index contains both (u, v) and (v, u) and has no duplicates."""
    if edge_index.numel() == 0:
        return edge_index
    rev_edges = edge_index[[1, 0]]
    all_edges = torch.cat([edge_index, rev_edges], dim=1)
    all_edges = torch.unique(all_edges, dim=1)
    # Remove self loops
    mask = all_edges[0] != all_edges[1]
    return all_edges[:, mask]


def generate_homophilic_edges(
    labels: np.ndarray,
    n_nodes: int,
    avg_degree: int,
    homophily: float = 0.75,
    seed: int = 42
) -> torch.Tensor:
    """Generate undirected edges with target homophily."""
    rng = np.random.default_rng(seed)
    edges = set()
    benign_nodes = np.where(labels == 0)[0]
    spam_nodes = np.where(labels == 1)[0]

    for u in range(n_nodes):
        deg = max(1, rng.poisson(avg_degree))
        u_label = labels[u]
        same_pool = spam_nodes if u_label == 1 else benign_nodes
        diff_pool = benign_nodes if u_label == 1 else spam_nodes

        for _ in range(deg):
            if rng.random() < homophily and len(same_pool) > 1:
                v = rng.choice(same_pool)
            else:
                v = rng.choice(diff_pool) if len(diff_pool) > 0 else rng.choice(n_nodes)
            if u != v:
                edges.add((min(u, v), max(u, v)))

    edge_list = list(edges)
    if len(edge_list) == 0:
        return torch.empty((2, 0), dtype=torch.int64)

    src = [e[0] for e in edge_list]
    dst = [e[1] for e in edge_list]
    edge_index = torch.tensor([src, dst], dtype=torch.int64)
    return make_undirected(edge_index)


def generate_mock_clean_graph(
    n_nodes: int = 5000,
    spam_ratio: float = 0.15,
    f_meta: int = 32,
    seed: int = 42
) -> dict:
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)

    # 1. Labels y
    n_spam = int(n_nodes * spam_ratio)
    y_arr = np.zeros(n_nodes, dtype=np.int64)
    spam_indices = rng.choice(n_nodes, size=n_spam, replace=False)
    y_arr[spam_indices] = 1
    y = torch.tensor(y_arr, dtype=torch.int64)

    # 2. x_sem [N, 768] (with weak label signal)
    # Benign centered near 0, Spam shifted along initial dimensions
    x_sem_arr = rng.normal(loc=0.0, scale=1.0, size=(n_nodes, 768)).astype(np.float32)
    # Give spam nodes a distinctive signal in the first 64 dimensions
    x_sem_arr[spam_indices, :64] += rng.normal(loc=0.6, scale=0.3, size=(n_spam, 64)).astype(np.float32)
    # Normalize embeddings
    norms = np.linalg.norm(x_sem_arr, axis=1, keepdims=True) + 1e-8
    x_sem_arr = x_sem_arr / norms
    x_sem = torch.tensor(x_sem_arr, dtype=torch.float32)

    # 3. x_meta [N, F] (Feature 0 is text length, features 1..F-1 behavioral)
    x_meta_arr = np.zeros((n_nodes, f_meta), dtype=np.float32)
    # Feature 0: text length (benign reviews longer on average in YelpChi)
    text_len_benign = rng.lognormal(mean=4.5, sigma=0.6, size=n_nodes).astype(np.float32)
    text_len_spam = rng.lognormal(mean=3.8, sigma=0.5, size=n_nodes).astype(np.float32)
    x_meta_arr[:, 0] = np.where(y_arr == 1, text_len_spam, text_len_benign)

    # Other metadata features (ratings, rating deviation, review entropy, etc.)
    for f in range(1, f_meta):
        if f == 1:  # Rating (1..5)
            ratings = np.where(
                y_arr == 1,
                rng.choice([1, 5], size=n_nodes, p=[0.5, 0.5]),
                rng.choice([1, 2, 3, 4, 5], size=n_nodes, p=[0.1, 0.1, 0.2, 0.3, 0.3])
            )
            x_meta_arr[:, f] = ratings.astype(np.float32)
        else:
            shift = 0.4 if (f % 3 == 0) else 0.0
            x_meta_arr[:, f] = rng.normal(
                loc=np.where(y_arr == 1, shift, 0.0),
                scale=1.0,
                size=n_nodes
            ).astype(np.float32)

    x_meta = torch.tensor(x_meta_arr, dtype=torch.float32)

    # 4. Relations: RUR (review-user-review), RSR (review-star-review), RTR (review-time-review)
    edge_index_rur = generate_homophilic_edges(y_arr, n_nodes, avg_degree=4, homophily=0.80, seed=seed + 1)
    edge_index_rsr = generate_homophilic_edges(y_arr, n_nodes, avg_degree=8, homophily=0.70, seed=seed + 2)
    edge_index_rtr = generate_homophilic_edges(y_arr, n_nodes, avg_degree=5, homophily=0.75, seed=seed + 3)

    # 5. Splits: 60% train, 20% val, 20% test (stratified by class)
    perm_benign = rng.permutation(np.where(y_arr == 0)[0])
    perm_spam = rng.permutation(spam_indices)

    def split_indices(indices):
        n = len(indices)
        n_tr = int(0.6 * n)
        n_va = int(0.2 * n)
        return indices[:n_tr], indices[n_tr:n_tr + n_va], indices[n_tr + n_va:]

    tr_b, va_b, te_b = split_indices(perm_benign)
    tr_s, va_s, te_s = split_indices(perm_spam)

    train_idx = np.concatenate([tr_b, tr_s])
    val_idx = np.concatenate([va_b, va_s])
    test_idx = np.concatenate([te_b, te_s])

    train_mask = torch.zeros(n_nodes, dtype=torch.bool)
    val_mask = torch.zeros(n_nodes, dtype=torch.bool)
    test_mask = torch.zeros(n_nodes, dtype=torch.bool)

    train_mask[train_idx] = True
    val_mask[val_idx] = True
    test_mask[test_idx] = True

    # 6. review_ids
    review_ids = [f"rev_{i:06d}" for i in range(n_nodes)]

    clean_graph = {
        "x_sem": x_sem,
        "x_meta": x_meta,
        "y": y,
        "edge_index_rur": edge_index_rur,
        "edge_index_rsr": edge_index_rsr,
        "edge_index_rtr": edge_index_rtr,
        "train_mask": train_mask,
        "val_mask": val_mask,
        "test_mask": test_mask,
        "review_ids": review_ids,
    }
    return clean_graph


def generate_semantic_variant(
    clean_graph: dict,
    level: str,
    shift_ratio: float,
    seed: int = 101
) -> tuple[dict, pd.DataFrame]:
    """Generate semantic camouflage variant (sem_L1, sem_L2, sem_L3)."""
    rng = np.random.default_rng(seed)
    variant_name = f"sem_{level}"
    y = clean_graph["y"].numpy()
    spam_mask = (y == 1)
    n_nodes = len(y)

    x_sem_orig = clean_graph["x_sem"].numpy()
    benign_mean = x_sem_orig[y == 0].mean(axis=0, keepdims=True)

    x_sem_cam = x_sem_orig.copy()
    noise = rng.normal(0, 0.05, size=x_sem_cam[spam_mask].shape).astype(np.float32)
    # Shift toward benign mean
    x_sem_cam[spam_mask] = (
        (1.0 - shift_ratio) * x_sem_cam[spam_mask] +
        shift_ratio * benign_mean +
        noise
    )
    # Re-normalize
    norms = np.linalg.norm(x_sem_cam, axis=1, keepdims=True) + 1e-8
    x_sem_cam = x_sem_cam / norms

    # Slightly adjust text-length feature in x_meta (feature 0)
    x_meta_cam = clean_graph["x_meta"].clone()
    benign_len_mean = clean_graph["x_meta"][y == 0, 0].mean().item()
    spam_len = x_meta_cam[spam_mask, 0]
    x_meta_cam[spam_mask, 0] = (1.0 - shift_ratio) * spam_len + shift_ratio * benign_len_mean

    attacked_mask = torch.tensor(spam_mask, dtype=torch.bool)

    variant_graph = {
        "x_sem": torch.tensor(x_sem_cam, dtype=torch.float32),
        "x_meta": x_meta_cam,
        "y": clean_graph["y"].clone(),
        "edge_index_rur": clean_graph["edge_index_rur"].clone(),
        "edge_index_rsr": clean_graph["edge_index_rsr"].clone(),
        "edge_index_rtr": clean_graph["edge_index_rtr"].clone(),
        "train_mask": clean_graph["train_mask"].clone(),
        "val_mask": clean_graph["val_mask"].clone(),
        "test_mask": clean_graph["test_mask"].clone(),
        "review_ids": list(clean_graph["review_ids"]),
        "attacked_mask": attacked_mask,
        "variant": variant_name,
    }

    # Generate texts parquet for spam reviews
    spam_indices = np.where(spam_mask)[0]
    records = []
    for idx in spam_indices:
        r_id = clean_graph["review_ids"][idx]
        orig_vec = x_sem_orig[idx]
        new_vec = x_sem_cam[idx]
        cos_sim = float(np.dot(orig_vec, new_vec) / (np.linalg.norm(orig_vec) * np.linalg.norm(new_vec) + 1e-8))
        records.append({
            "review_id": r_id,
            "node_idx": int(idx),
            "original_text": f"MOCK spam review text for {r_id} with original promotional phrasing.",
            "rewritten_text": f"MOCK {variant_name} rewritten review text matching genuine style for {r_id}.",
            "cosine_sim": cos_sim,
        })
    df_texts = pd.DataFrame(records)
    return variant_graph, df_texts


def generate_topology_variant(
    clean_graph: dict,
    variant_name: str,
    p: float,
    hub_targeted: bool = False,
    seed: int = 202
) -> tuple[dict, list[dict]]:
    """Generate topology camouflage variant (topo_p10, topo_p30, topo_p50, topo_hub_p30)."""
    rng = np.random.default_rng(seed)
    y = clean_graph["y"].numpy()
    spam_indices = np.where(y == 1)[0]
    benign_indices = np.where(y == 0)[0]
    n_nodes = len(y)

    relations = [
        ("rur", clean_graph["edge_index_rur"]),
        ("rsr", clean_graph["edge_index_rsr"]),
        ("rtr", clean_graph["edge_index_rtr"]),
    ]

    new_edges_dict = {}
    edges_added_records = []

    for rel_name, edge_index in relations:
        edges_set = set()
        ei_np = edge_index.numpy()
        for i in range(ei_np.shape[1]):
            edges_set.add((int(ei_np[0, i]), int(ei_np[1, i])))

        # Calculate degrees
        degrees = np.bincount(ei_np[0], minlength=n_nodes)

        # High-degree benign nodes for hub attack
        if hub_targeted:
            benign_degs = degrees[benign_indices]
            thresh = np.percentile(benign_degs, 80) if len(benign_degs) > 0 else 0
            candidate_benign = benign_indices[benign_degs >= thresh]
            if len(candidate_benign) == 0:
                candidate_benign = benign_indices
        else:
            candidate_benign = benign_indices

        added_for_rel = []
        for u in spam_indices:
            deg = max(1, degrees[u])
            budget = int(np.ceil(p * deg))
            chosen_benign = rng.choice(candidate_benign, size=min(budget, len(candidate_benign)), replace=False)
            for v in chosen_benign:
                if (u, v) not in edges_set:
                    edges_set.add((u, v))
                    edges_set.add((v, u))
                    added_for_rel.append((u, v))
                    edges_added_records.append({
                        "src_node_idx": int(u),
                        "dst_node_idx": int(v),
                        "relation": rel_name
                    })

        all_edges = list(edges_set)
        if len(all_edges) > 0:
            src = [e[0] for e in all_edges]
            dst = [e[1] for e in all_edges]
            t_ei = torch.tensor([src, dst], dtype=torch.int64)
            new_edges_dict[f"edge_index_{rel_name}"] = make_undirected(t_ei)
        else:
            new_edges_dict[f"edge_index_{rel_name}"] = edge_index.clone()

    attacked_mask = torch.tensor(y == 1, dtype=torch.bool)

    variant_graph = {
        "x_sem": clean_graph["x_sem"].clone(),
        "x_meta": clean_graph["x_meta"].clone(),
        "y": clean_graph["y"].clone(),
        "edge_index_rur": new_edges_dict["edge_index_rur"],
        "edge_index_rsr": new_edges_dict["edge_index_rsr"],
        "edge_index_rtr": new_edges_dict["edge_index_rtr"],
        "train_mask": clean_graph["train_mask"].clone(),
        "val_mask": clean_graph["val_mask"].clone(),
        "test_mask": clean_graph["test_mask"].clone(),
        "review_ids": list(clean_graph["review_ids"]),
        "attacked_mask": attacked_mask,
        "variant": variant_name,
    }

    return variant_graph, edges_added_records


def generate_all_mock_artifacts(artifacts_dir: str | None = None) -> None:
    if artifacts_dir is None:
        artifacts_dir = get_artifacts_dir()

    os.makedirs(os.path.join(artifacts_dir, "graph", "variants"), exist_ok=True)
    os.makedirs(os.path.join(artifacts_dir, "camouflage"), exist_ok=True)
    os.makedirs(os.path.join(artifacts_dir, "predictions"), exist_ok=True)
    os.makedirs(os.path.join(artifacts_dir, "results"), exist_ok=True)

    print(f"Generating mock clean graph in {artifacts_dir}/graph/ ...")
    clean_graph = generate_mock_clean_graph(n_nodes=5000, spam_ratio=0.15, seed=42)
    clean_path = os.path.join(artifacts_dir, "graph", "yelpchi_graph.pt")
    torch.save(clean_graph, clean_path)
    print(f"Saved {clean_path}")

    # Save CSV edge lists for clean graph
    for rel in ["rur", "rsr", "rtr"]:
        ei = clean_graph[f"edge_index_{rel}"].numpy()
        df_edges = pd.DataFrame({"src_node_idx": ei[0], "dst_node_idx": ei[1]})
        csv_path = os.path.join(artifacts_dir, "graph", f"edges_{rel}.csv")
        df_edges.to_csv(csv_path, index=False)

    # 1. Semantic variants
    sem_configs = [
        ("L1", 0.35),
        ("L2", 0.70),
        ("L3", 0.95),
    ]
    sem_variants = {}
    for level, ratio in sem_configs:
        var_name = f"sem_{level}"
        print(f"Generating {var_name} ...")
        var_graph, df_texts = generate_semantic_variant(clean_graph, level, ratio)
        var_path = os.path.join(artifacts_dir, "graph", "variants", f"{var_name}.pt")
        torch.save(var_graph, var_path)
        sem_variants[var_name] = var_graph
        text_path = os.path.join(artifacts_dir, "camouflage", f"texts_{var_name}.parquet")
        df_texts.to_parquet(text_path, index=False)

    # 2. Topology variants
    topo_configs = [
        ("topo_p10", 0.10, False),
        ("topo_p30", 0.30, False),
        ("topo_p50", 0.50, False),
        ("topo_hub_p30", 0.30, True),
    ]
    topo_variants = {}
    for var_name, p, is_hub in topo_configs:
        print(f"Generating {var_name} ...")
        var_graph, edges_added = generate_topology_variant(clean_graph, var_name, p, hub_targeted=is_hub)
        var_path = os.path.join(artifacts_dir, "graph", "variants", f"{var_name}.pt")
        torch.save(var_graph, var_path)
        topo_variants[var_name] = var_graph
        csv_added = os.path.join(artifacts_dir, "camouflage", f"edges_added_{var_name}.csv")
        pd.DataFrame(edges_added).to_csv(csv_added, index=False)

    # 3. Combined variant: both_L3_p30
    print("Generating both_L3_p30 ...")
    both_var = {
        "x_sem": sem_variants["sem_L3"]["x_sem"].clone(),
        "x_meta": sem_variants["sem_L3"]["x_meta"].clone(),
        "y": clean_graph["y"].clone(),
        "edge_index_rur": topo_variants["topo_p30"]["edge_index_rur"].clone(),
        "edge_index_rsr": topo_variants["topo_p30"]["edge_index_rsr"].clone(),
        "edge_index_rtr": topo_variants["topo_p30"]["edge_index_rtr"].clone(),
        "train_mask": clean_graph["train_mask"].clone(),
        "val_mask": clean_graph["val_mask"].clone(),
        "test_mask": clean_graph["test_mask"].clone(),
        "review_ids": list(clean_graph["review_ids"]),
        "attacked_mask": clean_graph["y"] == 1,
        "variant": "both_L3_p30",
    }
    both_path = os.path.join(artifacts_dir, "graph", "variants", "both_L3_p30.pt")
    torch.save(both_var, both_path)
    print("All mock artifacts generated successfully!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate mock data for NeuroGraph-DB")
    parser.add_argument("--artifacts-dir", type=str, default=None, help="Directory to output artifacts")
    args = parser.parse_args()
    generate_all_mock_artifacts(args.artifacts_dir)
