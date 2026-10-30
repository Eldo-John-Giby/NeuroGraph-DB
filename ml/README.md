# Machine learning

The deployed model combines frozen RoBERTa text vectors, 14 review features and three single-layer GraphSAGE branches with text-conditioned relation attention and gated fusion. It assesses new review batches against approved historical context. See the [model card](../docs/MODEL_CARD.md).

## Controlled comparison

The current benchmark evaluates four model arms on the same real-data chronological split:

| Model | Inputs and fusion |
|---|---|
| Text only | Frozen 768-dimensional RoBERTa vectors, projection and classifier |
| Graph only | Fourteen features, one GraphSAGE branch per relation, learned global relation weights |
| Concatenation | The same text and graph branches joined directly before classification |
| NeuroGraph | Text-conditioned relation attention and gated fusion in the deployed architecture |

All arms use the same 28,305 training, 9,435 validation and 9,436 test reviews. Graph-enabled models share RUR/RSR/RTR earlier-to-later edges and the 50-neighbor cap. Text-enabled models share the verified frozen embeddings. The fixed optimization budget is AdamW, learning rate 0.001, weight decay 0.0001, hidden width 128, dropout 0.2, weighted cross entropy, up to 80 epochs and patience 12. Checkpoints and cutoffs are chosen by validation macro F1.

Seeds 42, 43 and 44 vary initialization, not split membership. The original deployed seed-42 checkpoint is retained and reproduced; additional runs train locally on CPU. The recorded method identifies the original GPU-training environment difference. Mean and sample SD measure training variation, not a confidence interval.

See [all measured results and method](../docs/benchmarks/README.md), [model definitions](models/matched_baselines.py), [trainer](benchmark_matched.py) and [reproduction commands](../docs/REPRODUCIBILITY.md).

## Data and artifact construction

The exact labelled source is `samygithub/collective-opinion-spam-detection/training_data.csv`: 47,176 real historical reviews. `build_yelpchi_inductive_graph.py` sorts by date/review ID, builds 14 label-free features and causal relations, and creates the chronological split. `train_yelpchi_inductive.py` fits the metadata scaler on training rows, freezes a pinned RoBERTa encoder, trains the graph/fusion model, and seals the bundle. The downloaded `testing_data.csv` is unlabelled and is excluded from supervised test metrics.

```sh
python ml/build_yelpchi_inductive_graph.py \
  --training-csv .kaggle/yelpchi-raw/training_data.csv \
  --output-dir artifacts/inductive_graph
```

The controlled benchmark verifies and reuses the exact cached serving tensors and split files. Build/run its local image using the [reproduction guide](../docs/REPRODUCIBILITY.md). It does not require paid cloud resources, re-encoding all text or changing production predictions.

## Relevant files

- `models/roberta_relation_gnn.py`: current deployed architecture.
- `models/matched_baselines.py`: controlled real-data ablations.
- `benchmark_matched.py`: fixed-plan training, validation selection, test metrics/curves and label-blind missing-context stress tests.
- `train_yelpchi_raw_multimodal.py`: earlier raw known-node experiment.
- `train_yelpchi_gnn_baseline.py`: earlier 32-feature MAT experiment.
- `../docs/runs/`: three historical experiment records, displayed separately from the matched ranking.

## Legacy prototype

`train.py`, `mock_data.py`, the older model classes and camouflage scripts retain the early synthetic experiment for fixture/research reference. The older 5,000-node near-perfect tables do not establish real-data performance. They are superseded by the recorded matched benchmark. The final model uses single-layer relation branches and weighted cross entropy, not the older multi-head/focal-loss specification. No real LLM camouflage robustness or automatic retraining is claimed.
