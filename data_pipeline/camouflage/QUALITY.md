# Camouflage Quality & Attack Verification Report

This report details the quantitative properties of the LLM semantic and topological camouflage attacks generated on the YelpChi dataset.

## 1. Semantic Camouflage Fidelity & Shift

| Variant | Review Count | Mean Cosine Sim | Std Cosine Sim | Min Sim | Max Sim |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `sem_L1` | 750 | 0.6697 | 0.0180 | 0.5882 | 0.7160 |
| `sem_L2` | 750 | 0.6687 | 0.0172 | 0.6142 | 0.7272 |
| `sem_L3` | 750 | 0.6679 | 0.0178 | 0.6045 | 0.7189 |

## 2. Topological Camouflage Edge Dilution

| Variant | Total Heterophilic Edges Added | RUR Added | RSR Added | RTR Added |
| :--- | :--- | :--- | :--- | :--- |
| `topo_p10` | 65487 | 61696 | 902 | 2889 |
| `topo_p30` | 195701 | 185796 | 1299 | 8606 |
| `topo_p50` | 324202 | 308921 | 1688 | 13593 |
| `topo_hub_p30` | 36596 | 26688 | 1300 | 8608 |
