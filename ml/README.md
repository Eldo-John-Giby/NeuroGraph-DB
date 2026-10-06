# ML Module

**Owner:** Eldo

## Overview

The `ml/` module implements the multimodal relation-aware fraud detection framework for **NeuroGraph-DB**. It jointly models review semantics extracted from frozen `roberta-base` (768-d embeddings) and heterogeneous graph topology on YelpChi (Review-User-Review, Review-Star-Review, and Review-Time-Review) via multi-head cross-attention.

---

## Model Architectures

1. **Text-Only MLP (`text_only.py` - Baseline A):**
   - 2-layer MLP with LayerNorm, ReLU, and Dropout ($p=0.2$) operating purely on RoBERTa embeddings $\mathbf{x}_{\text{sem}} \in \mathbb{R}^{768}$.
2. **Relation-Aware GNN (`gnn_only.py` - Baseline B1):**
   - Independent 2-layer GraphSAGE encoders per relation ($RUR$, $RSR$, $RTR$) over behavioral metadata $\mathbf{x}_{\text{meta}} \in \mathbb{R}^{32}$, producing separate representations $[H_{rur}, H_{rsr}, H_{rtr}]$ and a learned softmax-weighted fused representation $H_{\text{fused}}$.
3. **Concatenation Fusion (`concat_fusion.py` - Baseline B2):**
   - Naive multimodal fusion: $\text{concat}(H_{\text{sem\_proj}}, H_{\text{struc\_fused}}) \to \text{MLP}$.
4. **NeuroGraph (`neurograph.py` - Main Proposed Model):**
   - Multimodal cross-attention where the projected semantic text embedding acts as the single Query token ($[N, 1, d_{\text{model}}]$) attending to 4 structural Key/Value tokens: $[H_{rur}, H_{rsr}, H_{rtr}, H_{\text{fused}}]$ ($[N, 4, d_{\text{model}}]$).
   - Residual connection + LayerNorm + Feed-Forward Network + Dropout + 2-layer classification head.
   - Extracts attention distribution $[w_{rur}, w_{rsr}, w_{rtr}, w_{\text{fused}}]$ summing to 1 for interpretability.

---

## Paper Hyperparameter Specifications

| Hyperparameter | Value | Description |
| :--- | :--- | :--- |
| `d_model` | `128` | Model hidden representation dimension |
| `num_heads` | `4` | Number of multi-head cross-attention heads |
| `dropout` | `0.2` | Dropout probability across all layers |
| `optimizer` | `AdamW` | Optimizer |
| `lr` | `1e-3` | Initial learning rate |
| `weight_decay` | `1e-4` | Weight decay penalty |
| `loss_type` | `focal` | Focal loss to address YelpChi 85:15 class imbalance |
| `focal_gamma` | `2.0` | Focusing parameter $\gamma$ |
| `focal_alpha` | `0.75` | Minority class weighting factor $\alpha$ |
| `epochs` | `60` | Maximum training epochs |
| `patience` | `15` | Early stopping patience monitoring Val PR-AUC |
| `seeds` | `[42, 43, 44, 45, 46]` | 5 reproducible seeds for mean ± std reporting |
| `relations` | `["rur", "rsr", "rtr"]` | YelpChi relation set |

---

## Evaluation & Robustness Protocols

- **Metrics:** ROC-AUC (`roc_auc_score`), PR-AUC (`average_precision_score`), and F1-Macro.
- **Threshold Policy:** Decision threshold $\tau$ is chosen on the validation split of the **training variant** to maximize F1-Macro and applied **unchanged** to the evaluation variant on the test split (strictly zero test/adversarial leakage).
- **Protocol A (Standard Robustness):** Model trained on `clean` and evaluated on all camouflage variants:
  - Semantic Camouflage: `sem_L1` (light paraphrase), `sem_L2` (full rewrite), `sem_L3` (style-conditioned).
  - Topology Camouflage: `topo_p10`, `topo_p30`, `topo_p50` (heterophilic dilution), `topo_hub_p30` (hub targeting).
  - Combined Attack: `both_L3_p30` (`sem_L3` + `topo_p30`).
- **Protocol B (Adversarial Training):** Model trained directly on attacked variants (`sem_L3`, `topo_p30`, `both_L3_p30`) and evaluated on both the attack and clean distributions.

---

## Makefile Targets & CLI Usage

Run these commands from inside `ml/` or root:

```bash
# Generate synthetic mock data & all camouflage variants
make mock

# Run all pytest unit tests
make test

# Train all baseline and proposed models on clean YelpChi
make train-all

# Run complete robustness benchmark suite (Protocols A & B)
make robustness

# Run architectural ablation studies
make ablate

# Run attention distribution analysis & statistical significance tests
make attention

# Export predictions to parquet / PostgreSQL
make export
```

---

## Requests to Teammates

- **To Avaneesh (`data_pipeline/`):**
  - Please ensure that when the real YelpChi dataset is ingested, the generated `artifacts/graph/yelpchi_graph.pt` and variant `.pt` files strictly conform to the `ARTIFACT CONTRACT` validated by `ml/data.py`.
- **To Anubhav (`viz/` and `docs/`):**
  - Robustness summary CSV is saved to `artifacts/results/robustness_summary.csv`.
  - Attention distributions are saved to `artifacts/results/<run_id>/attention.parquet`.
  - Figures and plots are located in `ml/figures/`.
