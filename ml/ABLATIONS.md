# Ablation Studies Summary

Systematic architectural ablation on YelpChi (mean ± std over 5 seeds):

| Ablation Setting | ROC-AUC | PR-AUC | F1-Macro |
| :--- | :--- | :--- | :--- |
| **Full NeuroGraph (All Relations + Cross-Attn)** | 0.9983 ± 0.0021 | 0.9946 ± 0.0063 | 0.9909 ± 0.0081 |
| **No-Graph (Text-Only MLP)** | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 0.9988 ± 0.0011 |
| **No RUR (Remove Review-User-Review)** | 0.9998 ± 0.0002 | 0.9990 ± 0.0009 | 0.9972 ± 0.0010 |
| **No RTR (Remove Review-Time-Review)** | 0.9994 ± 0.0006 | 0.9979 ± 0.0019 | 0.9965 ± 0.0021 |
| **No RSR (Remove Review-Star-Review)** | 0.9994 ± 0.0004 | 0.9977 ± 0.0012 | 0.9961 ± 0.0020 |
| **Naive Concat Fusion (Concat instead of Cross-Attn)** | 0.9766 ± 0.0146 | 0.9260 ± 0.0563 | 0.9256 ± 0.0550 |
| **No-Text (GNN-Only)** | 0.9281 ± 0.0031 | 0.7210 ± 0.0162 | 0.8044 ± 0.0143 |
