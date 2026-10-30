# CSV analysis workflow

Authenticated users upload a UTF-8 CSV with required columns `review_id,reviewer_id,product_id,rating,review_date,review_text`. External identities are source-scoped keys, not internal database integers. Ratings must be integers 1–5; dates parse as ISO-8601 with UTC interpretation for timezone-free input; text must be nonempty. The backend enforces an 8 MiB file and 5,000-row limit.

## Intake and persistence

`POST /api/v1/batch-analyses` validates headers and rows, resolves authors/products, stores valid source reviews and creates a receipt plus per-row outcomes in a transaction. Invalid rows retain errors. Identical existing canonical records can be reused; changed content under an existing source review identity is rejected. Duplicate file retries recover the requester's prior receipt/run rather than inventing new identities or recomputing a completed result. Original filenames and upload fingerprints support saved history.

`GET /api/v1/batch-analyses` supports scoped history, pagination, filename search and status filtering. Researchers see their own history. Admins explicitly select all-user scope. Detail/results/graph/scoring enforce row ownership or ADMIN and return 404 for inaccessible private batches.

## Context and scoring

The upload form selects a permitted compatible snapshot. The final model uses `inductive-rur-rsr-rtr-v1`; the earlier known-node graph is intentionally incompatible. Administrator permission changes are audited. A new run requires verified artifacts and eligible context; missing or mismatched data returns an explicit error, never synthetic scores.

`POST /api/v1/batch-analyses/{id}/score` pins the model, snapshot and cutoff and invokes processing. The worker persists leases and run state, reads training-partition history without selecting labels, filters history to the earliest uploaded arrival, and stitches earlier upload rows into later rows. Frozen source snapshots remain unchanged. No automatic retraining occurs.

The model uses actual uploaded text, 14 numeric features and three directed relations: same reviewer, same product/rating, and same product within 30 days, each capped at 50 recent neighbors. Predictions, threshold decisions, relation weights, connected identities and feature/graph fingerprints are saved. A score at or above the validation-selected threshold is flagged for investigation, not proven fraudulent.

## Results and graph

`GET /api/v1/batch-analyses/{id}/results` returns saved row outcomes and predictions. `POST /api/v1/batch-analyses/{id}/graph` reconstructs the same relations, verifies the inference fingerprint, and upserts the relevant Neo4j projection. Graph inspection is independent of retraining or score recomputation. Unavailable Neo4j produces an explicit graph error rather than fabricated relationships.

The current processing endpoint executes the worker function synchronously with durable job state; a separate autonomous background worker is not claimed. General graph-sync queue records are also distinct from the implemented explicit batch/scenario projection functions.

## Evaluation and examples

The [matched benchmark](benchmarks/README.md) compares four architectures on the same 9,436 chronological test reviews. Temporal replay and live batches can supply different historical context; an unlabelled upload has predictions but no measured accuracy. The app's downloadable fresh-upload CSV demonstrates the workflow. Historical labelled test files may have already-ingested IDs and should not be presented as fresh upload examples.

Synthetic restaurant investigations are stored and projected separately with explicit provenance. Their known campaign membership and rating summaries demonstrate investigation; they do not provide measured ML performance or discovered ground truth.
