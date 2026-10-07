import os
import sys
import torch

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from data_pipeline.camouflage.semantic_attack import generate_semantic_attacks
from data_pipeline.camouflage.topology_attack import generate_topology_attacks



def build_all_variants():
    artifacts_dir = os.environ.get("ARTIFACTS_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "artifacts")))
    clean_pt = os.path.join(artifacts_dir, "graph", "yelpchi_graph.pt")
    clean_graph = torch.load(clean_pt, weights_only=False)

    variants_dir = os.path.join(artifacts_dir, "graph", "variants")
    os.makedirs(variants_dir, exist_ok=True)

    print("Generating semantic variants...")
    sem_res = generate_semantic_attacks()

    print("Generating topology variants...")
    topo_res = generate_topology_attacks()

    # 1. Save semantic variants (.pt)
    for var_name, data in sem_res.items():
        var_dict = {
            "x_sem": data["x_sem"],
            "x_meta": data["x_meta"],
            "y": clean_graph["y"].clone(),
            "edge_index_rur": clean_graph["edge_index_rur"].clone(),
            "edge_index_rsr": clean_graph["edge_index_rsr"].clone(),
            "edge_index_rtr": clean_graph["edge_index_rtr"].clone(),
            "train_mask": clean_graph["train_mask"].clone(),
            "val_mask": clean_graph["val_mask"].clone(),
            "test_mask": clean_graph["test_mask"].clone(),
            "review_ids": list(clean_graph["review_ids"]),
            "attacked_mask": data["attacked_mask"],
            "variant": var_name,
        }
        pt_path = os.path.join(variants_dir, f"{var_name}.pt")
        torch.save(var_dict, pt_path)
        print(f"Saved {pt_path}")

    # 2. Save topology variants (.pt)
    for var_name, edges_dict in topo_res.items():
        var_dict = {
            "x_sem": clean_graph["x_sem"].clone(),
            "x_meta": clean_graph["x_meta"].clone(),
            "y": clean_graph["y"].clone(),
            "edge_index_rur": edges_dict["edge_index_rur"],
            "edge_index_rsr": edges_dict["edge_index_rsr"],
            "edge_index_rtr": edges_dict["edge_index_rtr"],
            "train_mask": clean_graph["train_mask"].clone(),
            "val_mask": clean_graph["val_mask"].clone(),
            "test_mask": clean_graph["test_mask"].clone(),
            "review_ids": list(clean_graph["review_ids"]),
            "attacked_mask": clean_graph["y"] == 1,
            "variant": var_name,
        }
        pt_path = os.path.join(variants_dir, f"{var_name}.pt")
        torch.save(var_dict, pt_path)
        print(f"Saved {pt_path}")

    # 3. Save combined variant both_L3_p30 (.pt)
    both_dict = {
        "x_sem": sem_res["sem_L3"]["x_sem"].clone(),
        "x_meta": sem_res["sem_L3"]["x_meta"].clone(),
        "y": clean_graph["y"].clone(),
        "edge_index_rur": topo_res["topo_p30"]["edge_index_rur"].clone(),
        "edge_index_rsr": topo_res["topo_p30"]["edge_index_rsr"].clone(),
        "edge_index_rtr": topo_res["topo_p30"]["edge_index_rtr"].clone(),
        "train_mask": clean_graph["train_mask"].clone(),
        "val_mask": clean_graph["val_mask"].clone(),
        "test_mask": clean_graph["test_mask"].clone(),
        "review_ids": list(clean_graph["review_ids"]),
        "attacked_mask": clean_graph["y"] == 1,
        "variant": "both_L3_p30",
    }
    both_pt = os.path.join(variants_dir, "both_L3_p30.pt")
    torch.save(both_dict, both_pt)
    print(f"Saved {both_pt}")


if __name__ == "__main__":
    build_all_variants()