# viz Documentation

This directory contains the visualization, mock data generation, database synchronization, and query components for NeuroGraph-DB.

## Components

- **mock/**: Contains `seed_mock.py` which generates fake users, products, and reviews (including planted fraud rings and camouflage variants) for testing without a real Postgres backend. It creates fake predictions and robustness summaries.
- **sync/**: Contains `neo4j_sync.py` to synchronize data from PostgreSQL (or mock files) to Neo4j. It supports a `--subgraph` mode and handles topological camouflage variants (`--variant`).
- **cypher/**: Cypher queries (`queries.cypher`) to analyze fraud rings, camouflage behaviors, and neighborhoods in Neo4j.
- **sql/**: SQL queries (`explain_demos.sql`) and testing scripts (`run_explain.py`) for index performance analysis. `sql_equivalents.sql` shows relational mapping of Cypher logic.
- **app/**: A Streamlit dashboard (`streamlit_app.py`) for visualizing metrics, graph clusters, case studies, DB query execution times, and robustness under camouflage attacks.
- **tests/**: Pytest suite for the synchronization logic and syntax validation.

## Makefile Targets
- `neo4j-up`: Starts the Neo4j instance via docker-compose.
- `seed-mock`: Generates mock dataset in `mock_data/`.
- `sync`: Syncs the base dataset to Neo4j.
- `sync-variant`: Syncs data for a specific variant (e.g., `make sync-variant VARIANT=camo_1`).
- `app`: Runs the Streamlit dashboard.
- `explain`: Evaluates query performance before and after indexing.
- `test`: Runs the pytest suite.
