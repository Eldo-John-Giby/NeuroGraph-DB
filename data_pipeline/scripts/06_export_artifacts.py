"""
Exports finalized clean YelpChi graph artifacts adhering to the ARTIFACT CONTRACT.
Saves artifacts/graph/yelpchi_graph.pt and artifacts/graph/edges_{rur,rsr,rtr}.csv.
"""

import os
import torch
import pandas as pd


def export_clean_artifacts() -> str:
    raw_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "raw"))
    artifacts_dir = os.environ.get("ARTIFACTS_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "artifacts")))

    graph_dir = os.path.join(artifacts_dir, "graph")
    os.makedirs(graph_dir, exist_ok=True)

    topo = torch.load(os.path.join(raw_dir, "graph_topology.pt"), weights_only=False)
    x_sem = torch.load(os.path.join(raw_dir, "x_sem.pt"), weights_only=False)
    splits = torch.load(os.path.join(raw_dir, "splits.pt"), weights_only=False)

    clean_graph = {
        "x_sem": x_sem,
        "x_meta": topo["x_meta"],
        "y": topo["y"],
        "edge_index_rur": topo["edge_index_rur"],
        "edge_index_rsr": topo["edge_index_rsr"],
        "edge_index_rtr": topo["edge_index_rtr"],
        "train_mask": splits["train_mask"],
        "val_mask": splits["val_mask"],
        "test_mask": splits["test_mask"],
        "review_ids": topo["review_ids"],
    }

    out_pt = os.path.join(graph_dir, "yelpchi_graph.pt")
    torch.save(clean_graph, out_pt)
    print(f"Exported clean graph to {out_pt}")

    # Export edge CSVs
    for rel in ["rur", "rsr", "rtr"]:
        ei = clean_graph[f"edge_index_{rel}"].numpy()
        df_edges = pd.DataFrame({"src_node_idx": ei[0], "dst_node_idx": ei[1]})
        csv_path = os.path.join(graph_dir, f"edges_{rel}.csv")
        df_edges.to_csv(csv_path, index=False)
        print(f"Exported edges_{rel}.csv ({len(df_edges)} directed edges)")

    return out_pt


if __name__ == "__main__":
    export_clean_artifacts()