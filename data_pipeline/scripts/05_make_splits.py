"""
Creates stratified train (60%), val (20%), and test (20%) masks preserving spam ratio.
Saves split masks to data_pipeline/raw/splits.pt.
"""

import os
import torch
import numpy as np
import pandas as pd


def create_stratified_splits(train_ratio: float = 0.6, val_ratio: float = 0.2, seed: int = 42) -> dict:
    raw_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "raw"))
    proc_path = os.path.join(raw_dir, "processed_reviews.parquet")
    df = pd.read_parquet(proc_path).sort_values(by="node_idx").reset_index(drop=True)

    n = len(df)
    labels = df["label"].values
    rng = np.random.default_rng(seed)

    benign_idx = np.where(labels == 0)[0]
    spam_idx = np.where(labels == 1)[0]

    perm_benign = rng.permutation(benign_idx)
    perm_spam = rng.permutation(spam_idx)

    def split_arr(arr):
        n_arr = len(arr)
        n_tr = int(n_arr * train_ratio)
        n_va = int(n_arr * val_ratio)
        return arr[:n_tr], arr[n_tr:n_tr + n_va], arr[n_tr + n_va:]

    b_tr, b_va, b_te = split_arr(perm_benign)
    s_tr, s_va, s_te = split_arr(perm_spam)

    tr_indices = np.concatenate([b_tr, s_tr])
    va_indices = np.concatenate([b_va, s_va])
    te_indices = np.concatenate([b_te, s_te])

    train_mask = torch.zeros(n, dtype=torch.bool)
    val_mask = torch.zeros(n, dtype=torch.bool)
    test_mask = torch.zeros(n, dtype=torch.bool)

    train_mask[tr_indices] = True
    val_mask[va_indices] = True
    test_mask[te_indices] = True

    # Assign split column in dataframe
    df.loc[tr_indices, "split"] = "train"
    df.loc[va_indices, "split"] = "val"
    df.loc[te_indices, "split"] = "test"
    df.to_parquet(proc_path, index=False)

    splits_dict = {
        "train_mask": train_mask,
        "val_mask": val_mask,
        "test_mask": test_mask,
    }
    out_path = os.path.join(raw_dir, "splits.pt")
    torch.save(splits_dict, out_path)
    print(f"Created stratified splits: Train={train_mask.sum().item()}, Val={val_mask.sum().item()}, Test={test_mask.sum().item()}")
    return splits_dict


if __name__ == "__main__":
    create_stratified_splits()