# Cross-Attention Mechanism Analysis

Investigation of cross-attention token weighting $[w_{RUR}, w_{RSR}, w_{RTR}, w_{Fused}]$ for spam reviews under semantic and topology camouflage.

## Mean Attention Weights on Spam Test Set

| Variant | w_RUR | w_RSR | w_RTR | w_Fused |
| :--- | :--- | :--- | :--- | :--- |
| `clean` | 0.1966 ± 0.0207 | 0.2659 ± 0.0124 | 0.2850 ± 0.0144 | 0.2526 ± 0.0121 |
| `sem_L3` | 0.2660 ± 0.0278 | 0.2440 ± 0.0144 | 0.2625 ± 0.0138 | 0.2275 ± 0.0121 |
| `topo_p30` | 0.1971 ± 0.0209 | 0.2653 ± 0.0122 | 0.2851 ± 0.0145 | 0.2525 ± 0.0120 |
| `both_L3_p30` | 0.2659 ± 0.0278 | 0.2439 ± 0.0144 | 0.2625 ± 0.0138 | 0.2276 ± 0.0121 |

## Statistical Hypothesis Testing

- **Hypothesis (Attention Shift on Semantic Camouflage):** When review text is camouflaged (`sem_L3`), cross-attention dynamically adjusts attention toward structural relations.
  - Clean mean `w_fused`: 0.2526
  - `sem_L3` mean `w_fused`: 0.2275
  - Mean paired shift $\Delta w_{fused}$: -0.0250
  - Paired t-test: $t = -18.6933$, $p = 6.6202e-41$
  - Wilcoxon signed-rank test: $W = 199.0$, $p = 1.1733e-24$

## Attention Visualization

![Attention Distribution](figures/attention_distribution.png)
