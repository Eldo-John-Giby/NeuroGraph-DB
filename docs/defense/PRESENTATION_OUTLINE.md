# NeuroGraph-DB: class presentation outline

Use [BEGINNER_VIVA_GUIDE.md](BEGINNER_VIVA_GUIDE.md) for simple explanations and [LIVE_DEMO_SCRIPT.md](LIVE_DEMO_SCRIPT.md) for the current screen order. This outline replaces older notes containing outdated navigation and unsupported speed claims.

## 1. Problem and purpose

Suspicious reviews can look normal in isolation. We combine review language, numeric facts and relationships to help a human investigate. A model flag is not proof of fraud.

## 2. Real data and demonstration data

The exact final labelled source is Kaggle's `samygithub/collective-opinion-spam-detection`, `training_data.csv`: 47,176 rows, Y=6,243 and N=40,933. Labels reflect Yelp filtering and are imperfect research reference labels. Harbor Table and related example scenarios are separately labelled synthetic data.

## 3. Train, validation and test

Sort labelled rows by date and review ID: 28,305 train, 9,435 validation, 9,436 test. Training learns weights; validation chooses the checkpoint/cutoff; the final test measures performance. The downloaded unlabelled `testing_data.csv` is not the measured test set. Show exact local exports and their verification proof.

## 4. Neural model and graph relations

Frozen RoBERTa produces 768-number text embeddings. Fourteen numeric features include rating, earlier activity, writing style and time. One GraphSAGE branch per relation handles RUR (same reviewer), RSR (same product/rating) and RTR (same product within 30 days). Learned text-conditioned relation attention and gated fusion feed a classifier. Neighbor cap: 50 recent earlier reviews per relation.

## 5. Training controls

Seed 42, hidden dimension 128, dropout 0.2, AdamW, learning rate 0.001, weight decay 0.0001, class-weighted cross entropy. Up to 80 epochs, patience 12; recorded run completed 80 and selected epoch 74. Text encoding uses 192 tokens and batches of 64 during preparation; graph training is full-batch. These settings are not claimed to be globally optimal.

## 6. Final result and threshold

Final inductive test ROC-AUC **0.8105**, macro F1 **0.6624**, PR-AUC/average precision **0.4211**. Validation-selected threshold **0.7870707071**, chosen from 199 candidate cutoffs using macro F1. Explain false positives, false negatives, and why ROC-AUC is not ordinary accuracy. Scores are not separately calibrated probabilities.

## 7. Supporting benchmarks

| Experiment | ROC-AUC | Macro F1 | Boundary |
|---|---:|---:|---|
| Structured MAT GNN baseline | 0.9331 | 0.8078 | 45,954 nodes, 32 numeric features, no raw-text modality |
| Raw multimodal known-node model | 0.8439 | 0.6860 | 47,176 raw reviews, fixed known-node graph, random stratified split |
| Final inductive model | 0.8105 | 0.6624 | Chronological new-arrival evaluation |

Different protocols and representations prevent an apples-to-apples superiority claim. Show run records, manifests and fixed-review reproduction as evidence, not a guarantee of every future prediction.

## 8. Databases and architecture

Next.js frontend → FastAPI → PostgreSQL, neural runtime, Neo4j. PostgreSQL 16 is the authoritative record store; SQLAlchemy/Alembic implement the relational application. Neo4j 5 stores relationship projections; PyTorch/PyG perform inference. For uploaded analyses, graph reconstruction checks the saved inference fingerprint before projecting actual context links. Do not claim an unmeasured database speed advantage.

## 9. User workflow and human review

Upload → validation → scoring → saved result → Products & history. Each researcher can reopen their own analyses. Admins can explicitly view all-user history, create accounts, moderate feedback and change snapshot context permission. Review feedback retains human notes separately from machine predictions; it does not automatically relabel training data or retrain the model.

## 10. Database coursework evidence

Show the 23-table ERD, dictionary, normalization analysis, joins/constraints/transactions, the two aggregate views, `resolve_review_feedback` procedure, feedback audit trigger, and native backup/restore evidence. Explain the distinction between the Audit operations diagnostics screen and stored `audit_logs` rows. Reviewer catalog lists source authors; its endpoint currently requires login rather than ADMIN specifically.

## 11. Deployment and verification

Vercel Hobby hosts the frontend. One AWS EC2 instance hosts Dockerized FastAPI, PostgreSQL and Neo4j with Caddy HTTPS. CloudFormation/SSM support terminal provisioning and updates; private bundles stay outside Git. GitHub Actions tests/builds the application; do not claim it automatically deploys the backend. AWS hosting is finite Free-plan credit usage.

## 12. Contribution and limitations

Contribution: a working text-plus-graph investigation workflow with time-aware context, saved private history, reproducible model evidence and auditable human feedback. Existing RoBERTa/GraphSAGE/YelpChi techniques are reused, not invented. Limits: imperfect historical labels, domain shift, one recorded seed, uncalibrated scores and imperfect classification. Future work can include newer labelled data, repeated runs, fair component comparisons and stronger calibration.
