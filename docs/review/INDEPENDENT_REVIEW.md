# Independent review brief

Review target: NeuroGraph-DB, Database Systems Lab submission. This brief can be supplied to Claude or another independent reviewer. A review is requested; no external review result is claimed by this document.

## What to provide

1. The credential-free `NeuroGraph_DB_Review_Pack.zip` source snapshot, or the public repository: https://github.com/Eldo-John-Giby/NeuroGraph-DB.
2. Live site: https://frontend-three-snowy-10.vercel.app. Authenticated pages need a separately supplied course demo account. Never attach cloud keys, production administrator passwords, `.env` files or database dumps.
3. The supplied course rubric PDF. The review pack includes the public rubric mapping, not the original private course handout.
4. Screenshots or a recording of: upload, completed result, an opened review, graph context, saved history, human feedback, model comparison, admin registry and reviewer catalog. If the reviewer cannot operate an authenticated browser, ask it to identify that limitation rather than claim a live test.
5. Only if numerical reproduction is requested: the separate private ML artifact companion and the exact raw dataset obtained under its source terms. The review pack contains published metrics and logs but not large weights or raw review text.

## Request to give the reviewer

Act as a critical database professor, ML evaluation reviewer and usability tester. Review the attached source and the current website. Your task is to find concrete defects and unsupported claims, not to praise the project or guarantee marks. Keep observed defects, code-based inferences and untested concerns separate. Do not change cloud infrastructure, purchase anything, delete data, modify trained weights or send messages.

The main use case is: a researcher uploads review CSV data, understands which rows need investigation, inspects full review text and actual saved graph context, records human feedback, and reopens the same saved result later. An administrator additionally inspects model provenance, source author identities, user administration and operational diagnostics. Determine whether the implementation actually fulfils this use case.

Inspect these dimensions:

- **First-time comprehension:** After a CSV upload, can a novice explain submitted/accepted/scored/rejected counts, flagged vs not flagged, the saved cutoff and what to do next? Can they read full text, find high-score rows, inspect context, leave feedback and download results? Are failures and zero-result states useful?
- **Workflow correctness:** Verify author links apply the reviewer filter; feedback links prefill the internal review ID; history reopens stored predictions without rerunning; result filters/search/pagination work; CSV export includes all saved row outcomes. Check missing scores are never presented as genuine reviews.
- **UI/accessibility:** Review desktop and phone layouts, reading order, table scrolling, labels, contrast, keyboard access, native dialog focus/Escape behavior, long identifiers and empty/loading/error states. Do not infer accessibility compliance merely from a screenshot.
- **Scientific accuracy:** Trace report numbers back to saved results and code. Verify shared review membership, chronological boundaries, fixed labels, train-only fitting, validation-only checkpoint/cutoff selection, class weighting, all three seeds, frozen embeddings and relation rules. Look for leakage or test-based selection. Do not equate ROC-AUC with accuracy or risk score with calibrated probability.
- **Claims:** The matched four-arm study is text-only, graph-only, concatenation and NeuroGraph. The three older experiments differ in representation/protocol and are historical records, not a fair ranking. The earlier 5,000-node near-perfect prototype used label-conditioned synthetic fixtures and is not real-data performance evidence. Verify the site consistently preserves these distinctions.
- **Interpretation:** Concatenation has the highest three-seed mean; deployed NeuroGraph seed 42 has the highest seed-42 macro F1. Small differences and three seed SDs do not establish statistical superiority. Metadata and graph links were added together; no separate no-link retraining ablation was measured. Day-level date + review-ID tie ordering is a replay convention, not verified within-day arrival time. The existing holdout is reused, and original GPU vs added CPU training environments are recorded. Investigate any stronger claim.
- **Graph evidence:** Distinguish PostgreSQL source records, the Neo4j projection and the tensor graph used by the GNN. Connections and attention weights are descriptive model evidence, not proof of fraud or causal explanations. Verify node/edge display limits and counts.
- **Security/database:** Check ADMIN/RESEARCHER authorization on the server as well as menus; cross-user upload, prediction and feedback isolation; refresh/logout; CSV validation and spreadsheet formula escaping; ORM binding; FK/check constraints; transaction rollback; audited procedure/trigger; backups/restores. Catalog metadata and general run-list endpoints are authenticated reference endpoints; assess whether their visibility should be narrowed for production.
- **Purpose of administration:** Is the registry a useful provenance record rather than a duplicate benchmark dashboard? Does the author catalog help navigate review identities without inventing author-level fraud scores? Is 'registered', 'verified' and runtime 'available' clearly distinguished?
- **Deployment and rubric:** Read the actual GitHub workflow and successful logs. It automates CI tests/builds. Production frontend/backend release currently uses explicit CLI deployment; a test-gated automatic CD pipeline is not implemented. Evaluate the rubric's CI/CD +1 candidate honestly. Additional automated testing/audit logging supports a separate +1 candidate; an owned custom-domain bonus is not claimed. Do not guarantee 30/30 or all bonus marks.

Return:

1. A severity-ranked table: issue, affected page/file/line, evidence, reproduction steps, user/scientific impact, smallest justified fix, acceptance check.
2. A walkthrough from upload to a defensible human decision, explaining where a first-time user gets stuck.
3. A claim audit: supported / overstated / unsupported / not tested, with evidence links.
4. A rubric assessment with evidence and unresolved gaps; no invented marks.
5. A short must-fix-before-submission list and separate optional future work.
6. Explicitly list everything you could not inspect or reproduce. If no defect is found in a category, say what checks support that result.

## Reading map

| Concern | Files |
|---|---|
| First-time workflow and actual UI | `db-dashboard/frontend/app/components/InductiveBatchSection.tsx`, `app/products/[batchId]/page.tsx`, `app/reviews/submit/page.tsx`, `app/feedback/page.tsx` |
| Result counting/filter/export contracts | `db-dashboard/frontend/app/lib/result-helpers.ts`, `tests/result-helpers.test.cjs` |
| Admin tools and author navigation | `db-dashboard/frontend/app/models/page.tsx`, `app/reviewers/page.tsx`, `app/reviews/page.tsx` |
| Auth, server ownership and persistence | `backend/app/security.py`, `backend/app/api/batches.py`, `backend/app/api/feedback.py`, `backend/app/models.py` |
| Shared-test protocol and results | `docs/benchmarks/README.md`, `protocol.json`, `comparison.json`, `results.csv`, `runs/` |
| Training and model architecture | `ml/benchmark_matched.py`, `ml/models/matched_baselines.py`, `ml/models/roberta_relation_gnn.py`, `ml/train_yelpchi_inductive.py` |
| Live inference and context | `backend/app/services/inductive_yelpchi.py`, `backend/app/services/batch_analysis_graph.py` |
| Honest limitations and old result audit | `docs/MODEL_CARD.md`, `docs/MODEL_AUDIT.md`, `docs/INDUCTIVE_PROTOCOL.md` |
| Database/course evidence | `docs/submission/RUBRIC.md`, `REPORT.md`, `ERD.md`, `DATA_DICTIONARY.md`, `NORMALIZATION.md`, `evidence/` |
| Tests and release boundaries | `.github/workflows/ci.yml`, `docs/CI_AND_RELEASE.md`, `docs/REPRODUCIBILITY.md`, `deploy/aws/README.md` |

Paths abbreviated with `app/` or `tests/` in a row are relative to `db-dashboard/frontend/`; other paths are repository-relative. The source archive's commit is recorded in the review pack manifest. Use that exact revision when citing findings.
