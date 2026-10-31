# Final workflow and administration review

Reviewed 31 October 2026 against the live application, source and course-use workflow. This records the implementation review and browser checks; it is not a claim that Claude or another external reviewer has completed an independent assessment.

## Decisions and corrections

| Finding | User impact | Change |
|---|---|---|
| Model registry led with a historical known-node runtime and repeated benchmark content | An administrator could confuse historical availability with new-upload scoring, or expect model management controls | Keep as admin provenance: current inductive runtime first, checkpoint/preparation identity, actual scoring jobs; link the separate comparison page. Explicitly read-only |
| Reviewer directory promised fraud distributions and clustering while returning only identity metadata | Implied author-level classification that was not implemented | Keep as an admin source-identity lookup; remove invented risk/pending badges and conceptual detection claims; add catalog pagination, explicitly page-local filtering and direct internal-ID lookup |
| Author-to-review links supplied a query parameter that the review page ignored | Investigation opened unrelated review records | Apply the author query filter in the review page |
| CSV result emphasized technical provenance, 'Actual Fraud Score' and 'Cleared' | A novice could mistake a score for a known fact or a negative result for proof of authenticity | Lead with a plain-language summary and next action; display model risk score, flagged for human review and not flagged; explain limitations |
| Hardcoded cutoff, manifest fallback and snapshot facts | Displayed provenance could disagree with actual saved records | Use the recorded run cutoff and saved evidence; fetch snapshot/registry reference metadata; show missing values explicitly |
| Truncated review text and a graph-hash-focused overlay | Difficult to read and act on an individual result, especially on a phone | Native full-text dialog, recorded context counts, clearly qualified attention weights, direct feedback prefill and author-record link |
| Unfiltered long result table | Hard to find priority rows in a larger upload | Full-text/ID search, decision/import-state filters, score/CSV-row sort and 25-row pagination |
| No reusable result download | Users could not retain a simple review list | Export every saved row outcome with the exact score/cutoff and import errors, independently of display filters; neutralize spreadsheet formulas |
| Graph link count could include edges whose endpoints were outside the visible 200-node slice | Count could disagree with drawn links | Count and render only links between displayed endpoints; retain total available link count |
| Review records displayed score as a percentage and called available labels verified | Suggested probability calibration or unquestionable labels | Use 0–1 model risk score, saved decision wording, dataset-label availability and a clear interpretation note |

## Evidence checked

- Fifteen frontend regressions passed: ten session refresh/logout tests and five saved-result counting/filter/export tests. Rounded cutoffs never override persisted decisions; unscored rows never count as genuine; formula-like CSV text is escaped.
- Next.js lint, types and production build passed. Final application CI and deployment identities are recorded in `submission/evidence/usability-review.json`.
- Desktop 1440 × 1000 and phone 390 × 844 checked. At phone width the page measured 375 pixels, with wide tables contained in their own horizontal scroll area. Native review dialog text/actions fit and Escape dismissed it.
- Administrator batch #19 displayed 30 scored, 9 flagged, 21 not flagged. Flagged filtering showed nine rows; feedback opened with the correct internal review ID; author lookup #129 opened only its visible review record.
- Researcher account showed its own upload library and no admin menu. Direct registry UI navigation redirected to Model results. Access to another account's private batch returned 404.
- Uploading the unchanged sample recovered saved batch #17 with its original timestamp and three predictions; it did not create a new scoring result. The downloaded CSV contained three outcomes, two saved flagged decisions and the recorded cutoff. Its Neo4j graph loaded three reviews and three visible links.
- A historical failed import displayed no model decisions rather than presenting missing scores as safe reviews.

Screenshots: `submission/assets/saved-result-live.jpg`, `review-detail-live.jpg`, `model-registry-live.jpg`. These show actual production screens; no mock scores or production-weight changes were used for the UI revision.

## Remaining boundaries

The reviewer catalog's text filter is page-local, not global author-key search. General catalog/run metadata APIs are authenticated reference endpoints; the admin menu and registry screen do not by themselves establish admin-only backend access to those read endpoints. Cross-user private batch/prediction/feedback ownership remains server-enforced. A future production deployment should assess whether catalog metadata needs tighter visibility.

The ML score is uncalibrated and the upload has no known evaluation labels. Some ordinary-looking examples are flagged, so human investigation is necessary. Saved relation weights describe the model's computation; they do not explain fraud causally. CI tests/builds automatically, while production release is an explicit CLI step. Neither this review nor an independent review can guarantee a faculty score.
