# Ablation Studies Summary

Systematic architectural ablation on YelpChi (mean ± std over 5 seeds):

| Ablation Setting | ROC-AUC | PR-AUC | F1-Macro |
| :--- | :--- | :--- | :--- |
| **Full NeuroGraph (All Relations + Cross-Attn)** | 0.9960 ± 0.0006 | 0.9778 ± 0.0023 | 0.9515 ± 0.0067 |
| **No RUR (Remove Review-User-Review)** | 0.9952 ± 0.0006 | 0.9752 ± 0.0027 | 0.9533 ± 0.0067 |
| **No RTR (Remove Review-Time-Review)** | 0.9950 ± 0.0007 | 0.9742 ± 0.0033 | 0.9545 ± 0.0041 |
| **No RSR (Remove Review-Star-Review)** | 0.9949 ± 0.0006 | 0.9735 ± 0.0037 | 0.9500 ± 0.0090 |
| **No-Graph (Text-Only MLP)** | 0.9898 ± 0.0034 | 0.9560 ± 0.0120 | 0.9272 ± 0.0099 |
| **Naive Concat Fusion (Concat instead of Cross-Attn)** | 0.9906 ± 0.0037 | 0.9554 ± 0.0152 | 0.9268 ± 0.0165 |
| **No-Text (GNN-Only)** | 0.7683 ± 0.0140 | 0.3815 ± 0.0328 | 0.6510 ± 0.0171 |
