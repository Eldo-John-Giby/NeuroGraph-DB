# YelpChi Dataset & Graph Statistics

## 1. Node and Label Distribution

| Metric | Value |
| :--- | :--- |
| **Total Reviews ($N$)** | 5,000 |
| **Benign Reviews ($y=0$)** | 4,250 (85.0%) |
| **Spam / Fraud Reviews ($y=1$)** | 750 (15.0%) |
| **Unique Users** | ~2,000 |
| **Unique Products** | ~500 |
| **Feature Dimensions** | Semantic $\mathbf{x}_{\text{sem}} \in \mathbb{R}^{768}$, Behavioral $\mathbf{x}_{\text{meta}} \in \mathbb{R}^{32}$ |

---

## 2. Multi-Relational Graph Topologies

| Relation Code | Relation Semantic | Average Degree | Edge Density |
| :--- | :--- | :--- | :--- |
| **$R_{RUR}$** | Review-User-Review (Same Reviewer) | 4.2 | Sparse, Homophilic |
| **$R_{RSR}$** | Review-Same Rating-Review (Same Product & Rating) | 8.6 | Dense Clusters |
| **$R_{RTR}$** | Review-Temporal-Review (Same Product $\le$ 30 Days) | 5.1 | Temporal Bursts |

---

## 3. Train / Val / Test Partitioning

| Split | Node Count | Benign Count | Spam Count | Spam % |
| :--- | :--- | :--- | :--- | :--- |
| **Train** | 3,000 | 2,550 | 450 | 15.0% |
| **Val** | 1,000 | 850 | 150 | 15.0% |
| **Test** | 1,000 | 850 | 150 | 15.0% |