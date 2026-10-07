import os
import sys
import torch
import numpy as np
import pandas as pd

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)



def make_undirected(edge_index: torch.Tensor) -> torch.Tensor:
    if edge_index.numel() == 0:
        return edge_index
    rev = edge_index[[1, 0]]
    combined = torch.cat([edge_index, rev], dim=1)
    unique_edges = torch.unique(combined, dim=1)
    mask = unique_edges[0] != unique_edges[1]
    return unique_edges[:, mask]


def generate_topology_attacks() -> dict:
    artifacts_dir = os.environ.get("ARTIFACTS_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "artifacts")))
    clean_pt = os.path.join(artifacts_dir, "graph", "yelpchi_graph.pt")
    if not os.path.exists(clean_pt):
        import importlib
        export_mod = importlib.import_module("data_pipeline.scripts.06_export_artifacts")
        clean_pt = export_mod.export_clean_artifacts()


    clean_graph = torch.load(clean_pt, weights_only=False)
    y = clean_graph["y"].numpy()
    spam_indices = np.where(y == 1)[0]
    benign_indices = np.where(y == 0)[0]
    n_nodes = len(y)

    camo_dir = os.path.join(artifacts_dir, "camouflage")
    os.makedirs(camo_dir, exist_ok=True)

    configs = [
        ("topo_p10", 0.10, False),
        ("topo_p30", 0.30, False),
        ("topo_p50", 0.50, False),
        ("topo_hub_p30", 0.30, True),
    ]

    topology_results = {}

    for var_name, p, is_hub in configs:
        rng = np.random.default_rng(200 + int(p * 100) + (50 if is_hub else 0))
        edges_added = []
        new_edges_dict = {}

        for rel in ["rur", "rsr", "rtr"]:
            ei = clean_graph[f"edge_index_{rel}"].numpy()
            edges_set = set((int(ei[0, i]), int(ei[1, i])) for i in range(ei.shape[1]))
            degrees = np.bincount(ei[0], minlength=n_nodes)

            if is_hub:
                benign_degs = degrees[benign_indices]
                thresh = np.percentile(benign_degs, 80) if len(benign_degs) > 0 else 0
                candidates = benign_indices[benign_degs >= thresh]
                if len(candidates) == 0:
                    candidates = benign_indices
            else:
                candidates = benign_indices

            for u in spam_indices:
                deg = max(1, degrees[u])
                budget = int(np.ceil(p * deg))
                chosen = rng.choice(candidates, size=min(budget, len(candidates)), replace=False)
                for v in chosen:
                    if (u, v) not in edges_set:
                        edges_set.add((u, v))
                        edges_set.add((v, u))
                        edges_added.append({
                            "src_node_idx": int(u),
                            "dst_node_idx": int(v),
                            "relation": rel
                        })

            all_e = list(edges_set)
            src = [e[0] for e in all_e]
            dst = [e[1] for e in all_e]
            new_edges_dict[f"edge_index_{rel}"] = make_undirected(torch.tensor([src, dst], dtype=torch.int64))

        # Save added edges CSV
        csv_path = os.path.join(camo_dir, f"edges_added_{var_name}.csv")
        df_added = pd.DataFrame(edges_added)
        df_added.to_csv(csv_path, index=False)
        print(f"Generated {var_name} added edges CSV at {csv_path} ({len(df_added)} edges added)")

        topology_results[var_name] = new_edges_dict

    return topology_results


if __name__ == "__main__":
    generate_topology_attacks()