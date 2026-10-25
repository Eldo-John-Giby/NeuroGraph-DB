# NeuroGraph-DB ML and Data Audit

Audit date: 2026-10-23. Scope: current working tree, local artifacts, and nearby project/artifact folders searched read-only; no implementation changes made. Existing uncommitted edits to `data_pipeline/sql/01_schema.sql` and `db-dashboard/frontend/app/page.tsx` were preserved.

## Executive findings

- The current graph artifact is synthetic, not YelpChi. A direct tensor comparison showed that `artifacts/graph/yelpchi_graph.pt` exactly matches `ml.mock_data.generate_mock_clean_graph(n_nodes=5000, spam_ratio=.15, f_meta=32, seed=42)` for semantic vectors, metadata, labels, all edge sets, and splits.
- A separate YelpChi MATLAB dataset is available at `/Users/avaneeshchavan/VS Code/YelpChi Project/data/YelpChi.mat`, outside this repository. It has 45,954 nodes, 32 input features, 6,677 positive and 39,277 negative labels, and three 45,954-square relation matrices. SHA-256: `fedb35a8fa539b27866244d3515a47a76b20080cdacb33112da3458fd2487b42`; it matches the MAT payload inside adjacent `FraudYelp.zip`. The adjacent project's README points to a Google Drive source, but licensing/redistribution terms remain unverified. This source does not match the repository's 5,000-node 768+32-feature graph or its predictions.
- The alternative `data_pipeline/scripts/01_get_data.py` also generates fabricated records and template text. It does not download source data. `04_embed_text.py` attempts RoBERTa but catches every exception and silently substitutes vectors generated with access to `label`.
- The present benchmark numbers therefore do not establish performance on YelpChi. `ml/results_summary.md` reports a perfect text-only result (ROC-AUC and PR-AUC 1.0); the label-conditioned synthetic feature construction explains this result as potential target leakage.
- No compatible trained checkpoint was found in this repository or searched nearby project/artifact folders. The current `.pt` files are graph dictionaries, not weights. The adjacent older YelpChi notebook keeps best weights in memory only; its training cells have no execution outputs, its model families are GCN/GraphSAGE/GAT rather than NeuroGraph, and its CSV contains aggregate metrics but no per-review test predictions.
- Local `artifacts/` contains one graph, eight variant graphs, 635 prediction parquet files, and 636 metric JSON files. One saved NeuroGraph clean/clean run was independently recomputed from its parquet and graph labels: all 1,000 test IDs aligned, metrics matched the JSON to its four-decimal reporting precision, and thresholded labels matched. This verifies the stored evaluation record, not model inference, retraining, or source-data validity.
- The model is transductive/known-graph scoring. Training performs full-graph forward passes and applies loss only at train nodes. There is no supported feature/embedding/edge construction and scoring path for a truly unseen review.

## Data path: source to prediction

1. **Source data:** `data_pipeline/scripts/01_get_data.py` emits 5,000 default rows with sampled IDs, synthetic ratings/dates, fixed phrase templates, generated spam labels, and review-ID/product suffixes. It does not download source data. No raw source file exists under `data_pipeline/raw/`. A separate YelpChi MATLAB source is present in the neighboring project folder described above, but no preprocessing path connects it to this repository's graph artifacts.
2. **Ingestion:** `data_pipeline/scripts/02_ingest.py` loads the generated CSV, assigns node indices, persists `processed_reviews.parquet`, and optionally inserts rows in Postgres. See `data_pipeline/README.md` for documented invocation.
3. **Semantic vectors:** `data_pipeline/scripts/04_embed_text.py` sorts by `node_idx`, tokenizes to max length 128, takes RoBERTa-base CLS output, and L2-normalizes to 768 dimensions. On any exception it creates seeded Gaussian vectors and adds a distinct shift to the first 64 dimensions for label-1 rows. The saved graph vectors match the separate mock generator exactly, proving they are not RoBERTa outputs.
4. **Metadata:** `data_pipeline/scripts/03_build_graph.py::compute_behavioral_features` creates 32 dimensions: log text length, rating, absolute product-mean rating deviation, absolute user-mean rating deviation, log user review count, log product review count, then 26 proxy columns made from one of the first six features plus seeded noise. It standardizes each column over the complete dataset. However, the current graph artifact exactly matches `ml/mock_data.py`, whose 32 raw features are generated with label-dependent text lengths, ratings, and shifts; they are not the output of this preprocessing function.
5. **Graph edges:** `03_build_graph.py` creates undirected RUR edges among reviews by the same user (degree cap 30), RSR among same product and rating (cap 50), and RTR among reviews for a product within 30 days (up to 20 forward neighbors). These are constructed over all records before split masks are applied. Mock graph edges are instead generated homophilically using labels.
6. **Splits:** `05_make_splits.py` creates stratified 60/20/20 node masks. The saved graph has 3,000 train, 1,000 validation, 1,000 test. Splits are random node splits, not time-based or user/product-disjoint.
7. **Variants:** `ml/mock_data.py`, camouflage scripts, and prebuilt `.pt` variant artifacts alter features/edges while retaining labels, node IDs, and masks. These are in-sample node perturbations, not independent new reviews.
8. **Model/training:** `ml/train.py` dispatches to `text_only`, `gnn_only`, `concat`, or `neurograph`. AdamW and focal loss are defaults. Each epoch runs a full graph forward pass; loss is restricted to the train mask. Early stopping monitors validation PR-AUC and picks a threshold on validation data.
9. **Checkpoint:** best weights are retained only in memory and restored for evaluation. The code does not save model weights to disk. No model checkpoint exists in the current `artifacts/` tree.
10. **Evaluation/predictions:** `ml/train.py` scores every node in the evaluation graph, computes metrics only on its test mask, but writes train/validation/test probabilities and labels to parquet. `ml/evaluate.py` computes ROC-AUC, average precision, macro F1, and threshold selection. `ml/export_predictions.py` can upsert scores to the separate SQL `fraud_predictions` table.

## 768-dimensional semantic vector and 32-dimensional metadata

The intended semantic path is frozen `roberta-base` CLS embedding (768 values), max 128 tokens, L2 normalization. The failure fallback is a seeded random vector with a label-conditioned offset, so a run can silently report “embeddings” that encode the answer. The checked-in artifact matches the synthetic mock-vector generator, not the declared transformer path.

The intended pipeline metadata has six dataset-derived measurements and 26 noisy proxies, with whole-dataset mean/std normalization. This adds redundant dimensions and uses global statistics before splitting. More critically, the active mock artifact comes from a different implementation where metadata is generated directly from labels: spam text length and rating distributions differ and several dimensions receive a spam-specific mean shift. The tensor comparison against the generator confirms this exact origin.

## Leakage, duplicates, contamination, and inductive behavior

- **Direct target leakage in synthetic generation (critical):** both synthetic vector paths use `y` to create discriminative features. Synthetic review records also embed row IDs/product IDs in their review text.
- **Graph label homophily in mock data (critical):** mock edge construction explicitly uses labels to choose same-label neighbors. The graph model can exploit this construction.
- **Dataset duplication/template effects (high):** generated review texts are drawn from six benign and five spam templates; suffixes make most rows textually distinct but the language is highly duplicated. This is not natural YelpChi text.
- **Split contamination / transductive protocol (high):** graph edges and metadata are built using the complete node set and include train/validation/test neighbors. This is a valid transductive benchmark only if declared; it does not establish future or unseen-node generalization. Global metadata normalization also sees held-out rows.
- **Known-node-only inference (high):** current model APIs accept a whole feature matrix and fixed edge index dictionaries. There is no API that embeds an incoming review, constructs its metadata with training-fitted transforms, attaches it to an allowed graph, or returns a one-review prediction. A newly unseen node requires rebuilding/re-indexing the full graph and retraining or an explicitly designed inductive serving path.
- **Threshold selection:** threshold is selected on validation, then reused on test; this part of the training path is appropriate. Predictive outputs include all splits, so they must not be treated as test-only exports.

## Metric verification

`ml/results_summary.md` claims clean-set mean/std over seeds, including text-only ROC-AUC = 1.0000 and PR-AUC = 1.0000. The README states seeds `[42,43,44]`, while `ml/configs/default.yaml`, `neurograph.yaml`, and robustness defaults use five seeds `[42,43,44,45,46]`. The summary also presents per-model rows but local results include multiple repeated runs and do not provide a single authoritative provenance manifest.

Artifacts found in this repository: 636 `metrics.json`, 635 prediction parquets, 9 graph `.pt` files, no checkpoint. See [REPRODUCIBILITY.md](REPRODUCIBILITY.md) for exact search/recalculation commands. For `neurograph_clean_clean_43_20261013085246`, saved test metrics recomputed as ROC-AUC 0.9953, PR-AUC 0.9797, macro-F1 0.9649; all 1,000 review IDs aligned and thresholded labels matched. JSON stores metrics to four decimals. This does not reproduce inference without weights. No NeuroGraph metrics on authentic YelpChi are verified.

## Dataset licensing / dependencies / secrets / missing models

- No root `LICENSE` or dataset license/source attribution is present in this repository. The adjacent project README gives a Google Drive source for YelpChi; dataset license and redistribution/usage terms remain unverified.
- Python dependency files are split by module; `transformers` is absent from `ml/requirements.txt` even though RoBERTa is loaded dynamically. `neo4j` and `streamlit` are needed by viz but absent from its requirements file (viz requirements is just a list of assorted Python packages and ends in a literal `\n` on inspection). The frontend lockfile is present; backend uses Prisma/Express, not FastAPI/SQLAlchemy.
- Development credentials are hardcoded in Compose/CLI defaults (`neuro/neuro`, `neo4j/neurograph123`), and `db-dashboard/backend/middleware/auth.js` falls back to a fixed JWT secret. `db-dashboard/backend/prisma/seed.js` contains demo passwords. These are local demo values, not evidence of production-safe secret handling.
- No compatible NeuroGraph weights/checkpoint exist in this repository or the searched adjacent YelpChi project. Other project checkpoints found in `CN_Project/artifacts/` are an unrelated 8-node spatial GCN-GRU forecasting model. Metrics JSON and predictions cannot replace a checkpoint for inference.

## Verified commands and outcomes

- `pytest -q ml/tests` — **10 passed**, 182 dependency deprecation/future warnings.
- Tensor comparison of saved graph with `generate_mock_clean_graph(..., seed=42)` — exact equality for `x_sem`, `x_meta`, `y`, all three edge indices, and all three masks.
- Prediction metric recomputation — one saved run matched its JSON metrics and labels at four-decimal reporting precision, and labels matched exactly (details above).
- Read-only `find` over this repository and nearby `VS Code` projects, excluding environments and dependency directories — no compatible NeuroGraph/YelpChi model checkpoint found. Here, `.pt` files are graph artifacts; unrelated `CN_Project` state dicts have incompatible forecasting layers.
- Adjacent YelpChi source inspection — MAT shape/label counts and SHA-256 recorded above; no matching NeuroGraph preprocessing output, checkpoint, or per-review predictions.

These checks confirm unit tests and one artifact-level metric calculation only. They do not validate real-data preprocessing, database deployment, Neo4j sync, frontend/backend runtime, or published performance claims.

## File-by-file report

| Area / files | Status and evidence |
|---|---|
| `README.md`, `ml/README.md`, `ml/results_summary.md` | Descriptive claims and results; README seed count conflicts with configs. Metrics not tied to a canonical checkpoint/run manifest. |
| `data_pipeline/scripts/01_get_data.py` | Synthetic template generator, not data acquisition. |
| `data_pipeline/scripts/02_ingest.py` | CSV-to-Parquet/Postgres ETL; depends on fake generator when input missing. |
| `data_pipeline/scripts/03_build_graph.py` | Graph and 32-feature builder; whole-dataset transforms; graph edges include held-out nodes. |
| `data_pipeline/scripts/04_embed_text.py` | RoBERTa attempt with unsafe label-aware fallback; dependency undeclared. |
| `data_pipeline/scripts/05_make_splits.py` | Stratified random node splits, no group/time holdout. |
| `data_pipeline/scripts/06_export_artifacts.py` | Packages graph tensors for ML, but does not record provenance/config hashes. |
| `ml/mock_data.py` | Synthetic labels, features, graph homophily and variants; local graph exactly matches it. |
| `ml/data.py` | Validates tensor shapes/masks/indices and loads whole graphs. No single-node inference loader. |
| `ml/models/*.py` | Four model implementations exist; model-shape unit tests passed. Inference depends on fixed full graph. |
| `ml/train.py` | Full-batch transductive training; validation stopping/threshold; no checkpoint persistence; writes predictions for all splits. |
| `ml/evaluate.py`, `ml/robustness.py`, `ml/ablations.py`, `ml/attention_analysis.py` | Evaluation/experiment orchestration exists. Metrics lack checkpoint-linked reproducibility; robustness repeatedly trains runs. |
| `ml/export_predictions.py` | SQL upsert export path exists, but was not integration-tested against a live Postgres instance. |
| `data_pipeline/sql/01_schema.sql`, `02_indexes.sql` | Core relational schema/index DDL; moderate constraints, nullable label/scores, no score/label domains; local schema file has pre-existing uncommitted newline-only change. |
| `db-dashboard/backend/prisma/schema.prisma`, `server.js`, `advanced_sql.sql` | Separate Prisma schema/application API and demo advanced SQL (view/procedure/trigger). This is not the core SQL schema and no synchronization/migration contract ties them together. |
| `viz/sync/neo4j_sync.py`, `viz/cypher/*`, `viz/tests/test_sync.py` | PostgreSQL/mock-to-Neo4j batch sync code and Cypher queries exist. Sync has fallback-to-mock behavior and no audited live integration run. |
| `viz/app/streamlit_app.py`, `viz/sql/*` | Research dashboard/query benchmarks; several values are hardcoded display data. They are not proof of measured DB latency. |
| `db-dashboard/frontend/**` | React/Next dashboard and login present. Local page copy edits preserved; no end-to-end UI/API verification performed. |
| `artifacts/**` | Local generated graph, variants, metrics, predictions, camouflage files; ignored by Git. No model checkpoints. |
| `/Users/avaneeshchavan/VS Code/YelpChi Project/data/YelpChi.mat`, `fake-review-gnn.ipynb`, `results/grid_results.csv` | Nearby source dataset and older GCN/GraphSAGE/GAT experiment records. Notebook does not persist weights; results CSV has aggregate rows only and is not tied to this NeuroGraph graph/config. |

