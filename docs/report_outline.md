# Course Report: NeuroGraph-DB

## 1. Introduction and Problem Statement
- The challenge of multimodal fraud detection in review systems.
- Limitations of relying solely on text or purely on static topology.

## 2. Related Work
- Text-based fraud detection.
- Graph-based fraud detection.
- Existing camouflage attacks against graph neural networks.

## 3. Hybrid DB Design (PostgreSQL + Neo4j)
- Rationale for using PostgreSQL for relational schema and Neo4j for deep traversal queries.
- Architecture of the synchronization layer (`neo4j_sync.py`).

## 4. Schema Normalization Argument
- Why 3NF was chosen for Postgres.
- Translating the relational model into property graph semantics.

## 5. Indexing and EXPLAIN Results
- Performance of analytical queries in SQL before and after B-tree indices.
- Comparison with Cypher equivalents for path-finding.

## 6. Dual-Branch Cross-Attention Model
- Incorporating RoBERTa semantics with GNN structural data.

## 7. Camouflage Threat Model
- Semantic camouflage (LLM-based rewriting).
- Topology camouflage (injecting cross-links to benign nodes).

## 8. Experiments & Robustness Results
- Protocol A vs Protocol B.
- Metrics: AUC, F1-Macro, PR-AUC.

## 9. Case Studies
- Visualization of fraud rings.
- Attention shift analysis under attack.

## 10. Limitations & Future Work
- Scalability challenges with cross-attention.
- Real-time detection feasibility.
