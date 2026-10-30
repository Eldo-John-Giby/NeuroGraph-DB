# Controlled real-data model comparison

The four model arms use the same 47,176 historical review identities and the exact deployed chronological split: 28,305 train, 9,435 validation and 9,436 test. Every arm is evaluated against the same 1,251 spam and 8,185 nonspam test labels. The original deployed seed-42 NeuroGraph checkpoint is retained and reproduced.

## Deployed-seed comparison

These seed-42 results match the checkpoint shown on the website homepage. ROC-AUC is not classification accuracy. PR-AUC is implemented as average precision.

| Model | ROC-AUC | PR-AUC | Macro F1 | Validation cutoff |
|---|---:|---:|---:|---:|
| Text only | 0.7835 | 0.4035 | 0.6475 | 0.7425 |
| Graph only | 0.7373 | 0.2685 | 0.5974 | 0.7079 |
| Text + graph concatenation | 0.8109 | 0.4213 | 0.6592 | 0.6782 |
| NeuroGraph | 0.8105 | 0.4211 | 0.6624 | 0.7871 |

Concatenation has the highest seed-42 ROC-AUC and average precision, by small observed margins. The deployed NeuroGraph checkpoint has the highest seed-42 macro F1. These metrics answer different questions and do not establish a universal winner.

## Repeated training runs

Seeds 42, 43 and 44 vary initialization while retaining the same data split. Values below are mean ± sample standard deviation, not confidence intervals.

| Model | ROC-AUC | PR-AUC | Macro F1 |
|---|---:|---:|---:|
| Text only | 0.7821 ± 0.0015 | 0.4011 ± 0.0024 | 0.6499 ± 0.0022 |
| Graph only | 0.7389 ± 0.0016 | 0.2687 ± 0.0020 | 0.5983 ± 0.0020 |
| Text + graph concatenation | 0.8110 ± 0.0034 | 0.4222 ± 0.0099 | 0.6628 ± 0.0034 |
| NeuroGraph | 0.8084 ± 0.0033 | 0.4154 ± 0.0162 | 0.6589 ± 0.0033 |

Concatenation has the highest three-seed mean for all three headline metrics. Both combined arms outperform the single-modality arms in these recorded runs. NeuroGraph's text-conditioned attention does not demonstrate a consistent performance improvement over simple concatenation here. The small differences between the combined models are not presented as statistically established superiority. No production checkpoint was selected or replaced using these test results.

## Fixed conditions and intentional differences

All arms share the same raw-data fingerprint, review ordering, training/validation/test membership and label mapping. Text-enabled arms share frozen 768-dimensional RoBERTa vectors from revision `e2da8e2f811d1448a5b465c236feacd80ffbac7b`, masked-mean pooling and 192-token truncation. Graph-enabled arms share the same 14 scaled features and causal RUR/RSR/RTR relations, capped at 50 earlier neighbors each. The scaler was fitted on training data only.

The architectures intentionally remove or change components:

- Text only uses text vectors and an MLP, without metadata or relationships.
- Graph only uses metadata and three one-layer GraphSAGE branches, combined with learned global relation weights.
- Concatenation joins the text and graph representations directly.
- NeuroGraph uses the deployed text-conditioned relation attention and gated fusion.

All use hidden width 128, dropout 0.2, AdamW at learning rate 0.001, weight decay 0.0001, training-class-weighted cross entropy, up to 80 epochs and patience 12. Each checkpoint and one of 199 cutoffs from 0.01 to 0.99 are chosen by validation macro F1. Parameter counts and actual early-stopped epoch counts are recorded, not claimed equal. Test labels are used after validation selection. Sparse CSR propagation is tested against the ordinary edge representation; the deployed checkpoint's metrics reproduce within 1e-6.

This is a controlled architecture ablation, not a claim that every model receives identical modalities or is an equal-parameter replica. The earlier 32-feature MAT checkpoint is not renamed as the new 14-feature graph-only arm.

## Missing graph context

The frozen models are additionally evaluated after independently removing each link with probability 0.1, 0.3 or 0.5, with a fixed label-independent seed. Cutoffs are retained; no adversarial retraining occurs. Text-only results remain unchanged because text-only consumes no graph. This measures missing-context sensitivity. It does not demonstrate robustness to real coordinated attackers or LLM rewrites.

## Historical records

The website displays all three earlier experiment records separately:

| Record | Data and protocol | ROC-AUC |
|---|---|---:|
| Structured MAT GNN | 45,954 rows, 32 features; stratified random 27,572 / 9,191 / 9,191 split; known nodes | 0.9331 |
| Earlier raw multimodal | 47,176 rows; stratified random 28,305 / 9,435 / 9,436 split; known nodes | 0.8439 |
| Deployed inductive checkpoint | 47,176 rows; chronological 28,305 / 9,435 / 9,436 split; temporal replay | 0.8105 |

The MAT source is `zhouxuanmingchen/yelp-fraud-processed/YelpChi.mat`; both raw experiments use `samygithub/collective-opinion-spam-detection/training_data.csv`. Their row identities are not interchangeable. They are excluded from a shared ranking because the first two have different representations or evaluation rules. Their records remain in [docs/runs](../runs/). The deployed checkpoint is also the NeuroGraph seed-42 arm in the new matched comparison.

## Provenance and reproduction

The exact raw source is Kaggle `samygithub/collective-opinion-spam-detection/training_data.csv`, SHA-256 `dbd3769b608bf249ed484f87d291e5d73f4988fd33e26f1bb96a50e8cdd418c8`. The downloaded `testing_data.csv` has no labels and did not produce these metrics. Metadata maps the source's `rating_OhNo` column to rating. Y maps to 1/spam, N to 0/nonspam.

- [Recorded protocol](protocol.json) was written before the additional training runs and fingerprints the code, source, graph and saved split files.
- [Full report and curves](comparison.json), [flat results](results.csv) and [per-run logs, selection and manifests](runs/) preserve the measured evidence.
- Private checkpoints and per-review prediction arrays remain under `artifacts/matched_benchmark/temporal_v1`, outside Git. Their hashes are recorded. They are not required merely to display the published report.
- The frontend's `public/benchmarks/comparison.json` is byte-identical to the report here. No performance values are handwritten into chart components.
- [Reproduction commands](../REPRODUCIBILITY.md), [trainer](../../ml/benchmark_matched.py), [model definitions](../../ml/models/matched_baselines.py) and [publication verifier](../../scripts/publish_benchmark.py).

The original checkpoint was GPU-trained; added runs use CPU with the same optimization controls. The published record discloses that environment difference. The seeded initialization and artifact verification support repeatability, not guaranteed bitwise identity across hardware/library versions.

## Interpretation limits

This is a retrospective comparison using the existing holdout, not a new independent blind dataset. Source timestamps have day-level resolution; review-ID ordering within a day defines a deterministic replay rather than a verified real arrival sequence. Combined-vs-text-only gains may reflect numeric features as well as links; a separate no-link retraining ablation was not measured. Three seeds describe training variation on one fixed split, not uncertainty over all future datasets. The Yelp filtering reference labels are imperfect. Replay can use earlier unlabelled arrivals; a live upload's fixed snapshot and batch can supply less history. New user files without true labels have predictions but no measured accuracy. Attention is not causal proof, and scores are not separately probability-calibrated.

The old 5,000-node synthetic fixture and near-perfect Protocol A/B tables are superseded. Label-conditioned synthetic features and links cannot establish real-data detection or LLM camouflage robustness. See [the provenance audit](../MODEL_AUDIT.md).

## Sources

- [YelpChi dataset author and label provenance](https://shebuti.com/yelpchi-dataset/).
- [GraphSAGE by Hamilton, Ying and Leskovec](https://arxiv.org/abs/1706.02216).
- [RoBERTa by Liu and colleagues](https://arxiv.org/abs/1907.11692).
- [scikit-learn average precision definition](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html).
