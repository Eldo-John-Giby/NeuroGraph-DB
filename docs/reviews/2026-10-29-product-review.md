# NeuroGraph product and evidence review — 29 October 2026

## Main finding

The system's strongest work was buried underneath a synthetic example and raw database catalogs. Its actual value is a verified model, authenticated CSV scoring, preserved predictions, and inspectable graph evidence. The interface should follow that order.

## Findings and changes

| Finding | Impact | Implemented response |
| --- | --- | --- |
| Synthetic restaurant evidence occupied the first screen | Visitors could reasonably mistake a scripted scenario for the final ML result | Lead with the verified final inductive model and its held-out metrics; move the synthetic workflow to Example investigation |
| The final model was less visible than the earlier transductive model | Different evaluation protocols were easy to conflate | Separate the final inductive temporal replay from the known-node multimodal reference benchmark; explain why the scores are not directly comparable |
| Products listed training-corpus IDs and a hardcoded “Active” cluster state | The catalog did not answer the user's main question: where are my files and results? | Replace it with a personal analysis library, filenames, statuses, real scored/flagged counts, search, filters, pagination, and stable links to saved results |
| Batch listing was global although result endpoints enforced ownership | Private upload metadata leaked, and researchers could select a batch they could not open | Default every account, including admins, to its own uploads; reserve the explicit all-users view for administrators; also restrict private raw-review and prediction access |
| Upload filename was not stored | Users could not identify old work reliably | Add a nullable filename field through an additive migration. Preserve old records; acquire their real filename on an identical owner retry rather than inventing names |
| The older graph appeared as a disabled dropdown choice | A correct scientific restriction looked like a broken feature | Select only compatible historical context automatically, offer a selector only for multiple compatible contexts, and explain the older graph's known-node limitation |
| Benchmark relationship explanations were inferred from score thresholds | Claimed attention evidence was not present in the API response | Remove those explanations. Keep attention weights and neighborhood evidence only where the inductive API actually returns them |
| Multiple navigation items were active for the upload route | Users lost their location | Match Review records exactly and reserve the nested upload route for its own navigation item |
| An N tile and starter favicon did not explain the project | Brand identity looked unfinished | Create one connected-review graph mark with a verification badge; use it in navigation, login, SVG/ICO favicons, and Apple icon |
| Generic graph-sync jobs have no running queue worker | An admin could mistake a queued maintenance job for a working scoring feature | Remove this incomplete tool from primary navigation. Preserve its route and records for maintenance. Saved CSV relationship graphs remain the supported graph workflow |
| Reviewer cards labelled missing fields as active/flagged counts | Missing values looked like measured zeroes | Replace those claims with explicit unavailable labels and label counts as page-scoped |

Additional browser findings: sign-out could leave a cached protected page loading, so unauthenticated navigation now performs a clean transition to login. The uploaded-review graph defaulted to RSR, which hid valid temporal links; it now starts with all relation types and reports the number of visible links.

## Information architecture

1. **Model results:** final verified performance, evaluation protocol, manifest/reproduction proof, recent completed analyses.
2. **Upload & analyze:** one file, automatic valid context, actual inference, then a saved result.
3. **Products & history:** only the current user's files by default; explicit administrator all-users mode.
4. **Saved analysis:** persistent URL, saved predictions, decisions, import failures, attention weights and graph evidence; opening a completed record never starts inference.
5. **Benchmark evidence:** the earlier known-node model and its reproducibility tools.
6. **Example investigation:** clearly synthetic campaign, charts, member evidence and Neo4j projection.
7. **Administration:** model registry, reviewer catalog, user management and audits.

## What should be highlighted

- Final inductive temporal replay: test ROC-AUC **0.810486**, F1-macro **0.662444**, PR-AUC **0.421073**, on **9,436** unseen test reviews. Threshold **0.787071** was selected using validation data.
- These are verified bundle metrics, not computed accuracy on an arbitrary uploaded CSV. Unlabelled uploads cannot establish accuracy.
- The graph and RoBERTa embeddings are real inference inputs. Evidence is tied to a saved inference run, model identity, and snapshot.
- Per-review scores support investigation. A flag is not proof of fraud, and a below-threshold decision is not a guarantee of authenticity.
- A synthetic scenario demonstrates how to inspect coordinated behavior. It does not independently validate the model.

## Retained strengths

The explicit real/synthetic provenance distinction, fixed-review reproduction, model and graph hashes, validation-selected threshold, actual text encoder, durable saved predictions, and authenticated roles are valuable. Keep those checks, while moving technical IDs into supporting detail instead of making them the main user flow.

## Practical limitations and follow-up

- Free hosting uses credits and has limited lifetime/capacity; these interface improvements do not make it unlimited hosting.
- Original filenames cannot be reconstructed perfectly for older uploads. The library identifies them by saved batch ID until an identical upload supplies the real filename.
- The generic graph-maintenance queue is unfinished. It is not the CSV inference path and is not advertised as a live feature.
- Model quality remains an empirical limitation: macro F1 and PR-AUC show meaningful error rates. Future model work should investigate calibration, per-class error analysis, drift, and externally labelled validation rather than increasing claimed confidence in the UI.
- This change does not retrain the model or alter its decision threshold, weights, historical snapshot, or stored predictions.

## Validation

Backend regression tests cover account isolation, admin visibility, original filename preservation, pagination/search/status filters, genuine model metadata, duplicate review reuse, conflict rejection, scoring, and the synthetic example. Frontend checks include production compilation, lint/types, authentication-refresh regressions, and live researcher/admin workflow verification. Final execution results are recorded with the deployment.

Final checks passed: **59 backend tests**, **10 authentication regressions**, production lint/type checks, and the production build. Live checks covered two researcher CSVs, filename search, private histories, explicit admin visibility, saved-run reuse, graph projection, upload-to-result navigation, custom icon assets, and the final-model homepage. Existing hosting stayed on the AWS Free plan and Vercel Hobby.
