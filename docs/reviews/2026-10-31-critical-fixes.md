# Submission critical review fixes

The independent review was checked against source revision `c9a8eb8`. Only submission-critical fixes and necessary verification were included. This note describes locally tested changes, not a completed production deployment or hosted CI run for those changes.

| Review finding | Action |
|---|---|
| 1 Cross-user import namespace collisions | Server-generated authenticated-user source namespaces for CSV and single-review intake; safe long-name handling; existing receipt recovery preserved for the original owner. Regression tests cover identical and conflicting files, separated review/author/product identities, private visibility and namespace impersonation. No schema migration or rewrite of prior results. |
| 2 Training budget | README, model card, benchmark method and final report disclose one full-batch step per epoch, all nine text-enabled runs hitting 80 steps, and lack of established convergence. Existing run records and trained weights remain unchanged. |
| 3 Reference context | UI and documentation explain that ordinary uploaded identities are disjoint from Yelp reference identities, making live relational evidence and counts within-file. The snapshot remains a compatibility/eligibility gate. Cold-context accuracy has not been measured separately; pre-reference files can fail eligibility. No new simulation is claimed. |
| 4 Base rate | The flag summary explains that rare spam can mean a larger share of false positives. The model card/report disclose test precision 39.9% and recall 44.2%, without promising those rates transfer to a new user file. |
| 5 Empty relation weights | The review dialog calls the three-way weights a relation gate and shows no percentage for zero-neighbor or unknown-context relations. Visible weights are not renormalized; scores and model computation are unchanged. |
| 6 Snapshot contract | Both scope key and relation schema must match. Intake, scoring, runtime and frontend enforce the stricter rule. Tests cover one-field-only mismatches at each backend boundary. |
| 8 CI revision evidence | GitHub already had a successful run for the exact reviewed revision: run 41174270640 on c9a8eb8. The old evidence was stale and has been refreshed. That remote run does not cover the subsequent local fixes; local results are recorded separately. |

## Verification

- Full backend with private bundles and an isolated disposable PostgreSQL database: **93 passed, no failures or skips**.
- Clean-checkout simulation without private bundles, with a fresh disposable PostgreSQL database: **81 passed, 12 explicit bundle-dependent skips, no failures**.
- Frontend authentication, CSV import and saved-result regressions: **29 passed**; lint and Next.js production build passed.
- Scientific matched-benchmark contracts: **6 passed**, including recorded prediction metrics and shared split checks. No retraining.
- Real encoder smoke test: three unknown CSV reviews scored through the pinned cached RoBERTa encoder and verified GNN, with no embedding stub or network access. Evidence counts matched the within-file RSR/RTR edges; identical retry recovered the same batch. Registration/history import and prediction writes used only a disposable in-memory database, never the running project/production databases.

Machine-readable details and implementation fingerprints are in `docs/submission/evidence/critical-fixes.json`. Local full XML and smoke artifacts are in ignored `output/verification/critical-fixes-2026-10-31/`.

## Deliberately deferred

No longer-budget training, extra architecture arm, more seeds, calibration, bootstrap study, cold-context experiment, asynchronous queue redesign, prediction immutability trigger, auth redesign or index changes were added. Those were outside the requested minimum. Existing legacy shared identities are preserved as historical records; new imports are isolated. The existing saved scores, threshold, weights and metric records were not replaced.

Release/synchronization is required before the live application contains these changes. The submission manifest identifies the exact locally packaged source revision. No push, cloud deployment or production-data mutation was performed in this fix batch.
