# Dataset statistics

| Source | Rows | Role |
|---|---:|---|
| Raw labelled YelpChi CSV | 47,176 | Current real-data training/evaluation source |
| Chronological training partition | 28,305 | Learn trainable model weights and metadata scaler |
| Chronological validation partition | 9,435 | Choose checkpoint and cutoff |
| Chronological test partition | 9,436 | Shared test for the controlled comparison |
| Downloaded unlabelled testing CSV | 20,219 | Excluded from supervised metrics |
| Earlier structured YelpChi MAT | 45,954 | Separate historical numeric-feature benchmark |

The labelled source contains 6,243 Y/spam and 40,933 N/nonspam labels. The source filename is `training_data.csv`; its rating mapping uses `rating_OhNo`. See the [model card](../docs/MODEL_CARD.md) for the exact fingerprint. The legacy 5,000-row fixture is synthetic and is not a sampled real YelpChi subgraph.
