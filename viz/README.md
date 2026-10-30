# Visualization utilities

The current website's charts and investigation views live in `db-dashboard/frontend/app`. Controlled model comparison charts consume the published `public/benchmarks/comparison.json`, generated from recorded real-data runs.

The deployed Neo4j projection is implemented in `backend/app/services/batch_analysis_graph.py`; synthetic examples use a separate service. PostgreSQL remains the authoritative record store.

This directory retains early mock-data and synchronization experiments. `mock/seed_mock.py` creates synthetic fixtures and generated display scores. Those scores and legacy synchronization fallbacks are not used to establish model performance or to serve the current website. Use the [current architecture](../docs/ARCHITECTURE.md) and [comparison method](../docs/benchmarks/README.md).
