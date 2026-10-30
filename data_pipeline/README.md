# Data preparation

Current real-data graph construction lives in `ml/build_yelpchi_inductive_graph.py`. The exact source is the labelled `training_data.csv` from `samygithub/collective-opinion-spam-detection`. The [model card](../docs/MODEL_CARD.md) and [matched evaluation](../docs/benchmarks/README.md) define the current columns, source fingerprint, chronological split and relationship rules.

This directory retains earlier SQL and synthetic fixture utilities. `scripts/01_get_data.py` generates artificial review records; despite its legacy function name it does not download YelpChi. The old 5,000-row examples and camouflage generators are not real-data benchmark evidence. The legacy embedding script now fails if RoBERTa cannot load; it never substitutes random vectors for model output.

`sql/` is an earlier prototype schema. The current application's schema is `backend/app/models.py` plus Alembic and is documented in the [23-table ERD](../docs/submission/ERD.md).

`docker-compose.postgres.yml` remains a convenient local PostgreSQL container. Production uses [deploy/aws/compose.yaml](../deploy/aws/compose.yaml). Do not run the legacy all-target to reproduce the final model; use the explicit current commands in the ML documentation.
