# Temporal review evaluation

The final model sorts the 47,176 labelled raw reviews by UTC date and review ID. It uses 28,305 training rows, 9,435 validation rows and 9,436 test rows. Scaling uses training rows only; loss uses training labels only. Validation chooses checkpoint and decision cutoff. Labels are stored separately from serving inputs.

Relations are directed from an earlier node to a later node, with stable ordering for equal dates. RUR uses the same reviewer; RSR the same product/rating; RTR the same product within 30 days. Each relation has at most 50 recent neighbors. Replay permits earlier unlabelled arrivals as context but never future-to-past links.

The [matched comparison](benchmarks/README.md) holds these identities, splits and relation rules fixed while varying the architecture. It reports three initialization seeds and keeps the deployed seed-42 checkpoint unchanged.

Live batch scoring uses an approved compatible snapshot's training-partition history, filtered to the batch cutoff, plus earlier rows in the same upload. It does not select reference labels or overwrite the snapshot. The available live context can differ from full chronological replay, so benchmark scores are not an accuracy promise for a user's file.

More specifically, user uploads have server-owned, user-specific source namespaces. Their internal author/product IDs do not match the Yelp reference IDs, even if the external strings happen to be identical. The reference snapshot therefore adds no same-author/product edges or prior counts for ordinary uploads; their effective relational context is earlier rows within that file. Snapshot presence still gates compatibility/eligibility, and files before the reference history's start may fail the current insufficient-context check. No simulated 30/500/5,000-row cold-context accuracy study has been measured. The full-replay scores must not be presented as such a study.

Both `context_scope_key` and `relation_schema_version` must match `inductive-rur-rsr-rtr-v1`, independently enforced by intake, scoring, runtime and frontend selection.

See `ml/build_yelpchi_inductive_graph.py`, `ml/train_yelpchi_inductive.py`, `backend/app/services/inductive_relations.py` and `inductive_yelpchi.py`. The current worker function is invoked by the processing endpoint with persistent job state; a separate autonomous worker service is not claimed.
