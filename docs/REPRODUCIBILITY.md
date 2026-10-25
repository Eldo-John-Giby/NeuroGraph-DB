# Phase 1 Reproducibility Check

Date: 2026-10-23. Read-only search and calculations; no checkpoint, predictions, metrics, embeddings, attention, or dataset were created or modified.

## Checkpoint search and compatibility

Commands run:

```bash
find . -type f \( -iname '*.pt' -o -iname '*.pth' -o -iname '*.ckpt' -o -iname '*.safetensors' -o -iname '*.onnx' \) -print
find '/Users/avaneeshchavan/VS Code' \
  \( -path '*/.git' -o -path '*/node_modules' -o -path '*/venv' -o -path '*/.venv' -o -path '*/site-packages' -o -path '*/.cache' \) -prune -o \
  -type f \( -iname '*.ckpt' -o -iname '*.pth' -o -iname '*.pt' -o -iname '*.safetensors' \) -print
```

No compatible NeuroGraph/YelpChi model checkpoint was found. The current repository `.pt` files are graph tensors/variants (`artifacts/graph/yelpchi_graph.pt` and `artifacts/graph/variants/*.pt`). Training code in `ml/train.py` keeps best weights in memory and does not save them. The nearby `YelpChi Project/fake-review-gnn.ipynb` saves `best_state` only in memory; its training cells have `execution_count: null`, no outputs, and its model families are GCN, GraphSAGE, and GAT rather than NeuroGraph. Its run loop writes aggregate CSV rows rather than weights or per-review prediction vectors.

The only other model-like `.pt` files found in nearby projects were `CN_Project/artifacts/gnn.pt` and `gru.pt`. Safe state-dict inspection showed 8-node adjacency/mask buffers and spatial-GCN/GRU forecasting layers (`spatial.weight` shape `[32,16]`, GRU input weights `[96,32]`, output head `[24,32]`); they are unrelated and incompatible.

Because no compatible checkpoint exists, **known-review model inference was not attempted**. No score was synthesized or passed off as reproduced.

## Dataset, graph, and run metadata

The neighboring project contains `/Users/avaneeshchavan/VS Code/YelpChi Project/data/YelpChi.mat` and `FraudYelp.zip`. The MAT file contains:

- `features`: `(45954, 32)` float64
- `label`: `(1, 45954)` int64, counts `{0: 39277, 1: 6677}`
- `homo`, `net_rur`, `net_rtr`, `net_rsr`: each `(45954, 45954)`
- SHA-256: `fedb35a8fa539b27866244d3515a47a76b20080cdacb33112da3458fd2487b42`

`unzip -p '/Users/avaneeshchavan/VS Code/YelpChi Project/FraudYelp.zip' YelpChi.mat | shasum -a 256` returned the same hash. The adjacent project's README attributes it to a Google Drive source. License/redistribution terms were not established. Its 45,954-node/32-feature representation does not match this repository's `artifacts/graph/yelpchi_graph.pt` `(5000, 768)` semantic and `(5000, 32)` metadata tensors; that graph was previously verified as an exact output of `ml.mock_data.generate_mock_clean_graph(seed=42)`. No preprocessing manifest connects the MAT file to this repository's graph.

The older adjacent `results/grid_results.csv` has 27 aggregate rows: GCN, GraphSAGE, and GAT × three graph variants × seeds 42–44. It has scalar metrics only, no per-review test predictions, checkpoint hashes, or matching NeuroGraph configuration. Those metrics cannot be independently recalculated from saved predictions.

## Independent metric recomputation from current saved predictions

Although a checkpoint is missing, one existing run's stored test metrics can be checked from its prediction parquet and graph labels. Exact command:

```bash
python - <<'PY'
import json, torch, pandas as pd
from sklearn.metrics import roc_auc_score, average_precision_score, f1_score

run = 'neurograph_clean_clean_43_20261013085246'
g = torch.load('artifacts/graph/yelpchi_graph.pt', map_location='cpu', weights_only=False)
p = pd.read_parquet(f'artifacts/predictions/{run}.parquet').sort_values('node_idx').reset_index(drop=True)
m = json.load(open(f'artifacts/results/{run}/metrics.json'))
mask = g['test_mask'].numpy()
y = g['y'].numpy()[mask]
test = p.loc[p.split.eq('test')]
assert len(test) == int(mask.sum())
assert test.review_id.tolist() == [g['review_ids'][i] for i in range(len(mask)) if mask[i]]
prob = test.fraud_score.to_numpy()
pred = test.predicted_label.to_numpy()
threshold = float(m['threshold'])
calculated = {
    'auc': roc_auc_score(y, prob),
    'pr_auc': average_precision_score(y, prob),
    'f1_macro': f1_score(y, (prob >= threshold).astype(int), average='macro'),
}
print('run', run, 'test_rows', len(test), 'ids_aligned', True)
print('threshold', threshold)
print('stored', {k: m[k] for k in calculated})
print('recomputed', {k: round(float(v), 4) for k, v in calculated.items()})
print('thresholded_labels_match', bool((pred == (prob >= threshold).astype(int)).all()))
print('sample_test_review', test.iloc[0][['review_id', 'node_idx', 'fraud_score', 'predicted_label']].to_dict())
PY
```

Observed output:

```text
run neurograph_clean_clean_43_20261013085246 test_rows 1000 ids_aligned True
threshold 0.08879396984924623
stored {'auc': 0.9953, 'pr_auc': 0.9797, 'f1_macro': 0.9649}
recomputed {'auc': 0.9953, 'pr_auc': 0.9797, 'f1_macro': 0.9649}
thresholded_labels_match True
sample_test_review {'review_id': 'rev_000001', 'node_idx': 1, 'fraud_score': 0.001383794704452157, 'predicted_label': 0}
```

Underlying files:

- `artifacts/predictions/neurograph_clean_clean_43_20261013085246.parquet`
- `artifacts/results/neurograph_clean_clean_43_20261013085246/metrics.json`
- `artifacts/graph/yelpchi_graph.pt`

The JSON metrics are rounded to four decimals; unrounded recomputed values differ by less than `0.00004`. The shown review value is an existing saved output and is **not** a model prediction reproduced from a checkpoint. This calculation confirms internal consistency of a synthetic-data artifact only. It does not validate README aggregate claims or performance on the adjacent YelpChi dataset.

## Post-audit checkpoint candidate (2026-10-23)

A later local Git commit, `349edcd948775404ab2a3046730ac0068b3d0821` (`feat(ml): add trained model checkpoint, graph artifact, and feature scalers for live inference`), added `artifacts/models/neurograph_best.pt`. This supersedes the earlier statement only as a file-presence finding; it does **not** establish a verified model bundle.

Observed SHA-256 values:

- Checkpoint: `faef1128d3c0af45d89873bb70e98034afd0999b4c0da49b3edefc13391c4409`
- Graph: `12b1e2e73400d4b0f6f3d3e9dc05271424d10e70aa37afc93ae6247045c2c7fb`

The file is a 61-entry PyTorch state dict. It loads strictly into `NeuroGraph` built from `ml/configs/neurograph.yaml` (`sem_dim=768`, `meta_dim=32`, `d_model=128`, four heads, `rur/rsr/rtr`) and runs on the current 5,000-node graph. Compatibility of tensor shapes is not provenance. The checkpoint has no embedded config, run ID, seed, threshold, preprocessing identifier, graph hash, or training manifest. The only scaler record is `artifacts/scalers/feature_scaler.json`; it describes 32 synthetic metadata columns without an immutable preprocessing code/config manifest. The graph was previously verified as generated by `ml/mock_data.py`.

Read-only comparison command:

```bash
python - <<'PY'
import glob, torch, yaml, pandas as pd
from ml.data import load_clean_graph
from ml.models import build_model
cfg = yaml.safe_load(open('ml/configs/neurograph.yaml'))
g = load_clean_graph()
m = build_model('neurograph', sem_dim=cfg['sem_dim'], meta_dim=cfg['meta_dim'],
                d_model=cfg['d_model'], num_heads=cfg['num_heads'],
                dropout=cfg['dropout'], use_sem_in_gnn=cfg['use_sem_in_gnn'],
                relations=tuple(cfg['relations']))
m.load_state_dict(torch.load('artifacts/models/neurograph_best.pt', map_location='cpu', weights_only=True), strict=True)
m.eval()
with torch.inference_mode():
    logits = m(g['x_sem'], g['x_meta'], {'rur':g['edge_index_rur'], 'rsr':g['edge_index_rsr'], 'rtr':g['edge_index_rtr']})
    p = torch.softmax(logits, dim=1)[:, 1].numpy()
distances=[]
for path in glob.glob('artifacts/predictions/neurograph_clean_clean_*.parquet'):
    saved = pd.read_parquet(path).sort_values('node_idx')
    if len(saved) == len(p):
        distances.append((abs(saved.fraud_score.to_numpy()-p).mean(), path))
print(sorted(distances)[:5])
PY
```

The closest saved NeuroGraph clean/clean prediction file had mean absolute score difference `0.2603106889`; it was `artifacts/predictions/neurograph_clean_clean_42_20261013072407.parquet` (tied with two other seed-42 output files). Thus the candidate does not reproduce the existing saved prediction run. The commit has no paired checkpoint-linked threshold or run metadata, and the existing threshold cannot be attributed to it. No prediction was written by this comparison.

**Serving decision:** this candidate is unverified and must not be registered as `verified` or served. The backend reports inference unavailable until a matching checkpoint, immutable config and preprocessing manifest, graph/split identity, and run/threshold evidence can be verified together. This audit addendum does not alter the model or data.

## Phase 1 blocker

No matching tuple of checkpoint, model config, preprocessing version, graph/split identity, and run metadata exists. The adjacent dataset does not repair that missing lineage. To unblock a real known-review reproduction, obtain the actual NeuroGraph checkpoint and complete training manifest, or decide separately to train a valid model after provenance and preprocessing are resolved. This audit did not train anything or alter the dataset.

## Follow-up: real bundle and repeatable reproduction attempt (2026-10-25)

The follow-up local artifact search still found no eligible real-data NeuroGraph run. The repository contains `artifacts/models/neurograph_best.pt`, `artifacts/graph/yelpchi_graph.pt`, and scaler files, but the prior evidence above establishes that the model candidate is unmanifested and the graph is generated from synthetic data. These files were not copied into a purported verified bundle and no training was run.

The adjacent `/Users/avaneeshchavan/VS Code/YelpChi Project/data/YelpChi.mat` is the only discovered YelpChi source artifact. The prior audit inspected its schema and found 32 numeric features, labels, and relation matrices; it has no review text suitable for generating real RoBERTa embeddings. The local license-file search (excluding dependency trees) found no repository `LICENSE`, `COPYING`, or `NOTICE` file, and the neighboring project `data/` folder likewise contains no license evidence. This does not establish the dataset's legal terms. No compatible source-text corpus, RoBERTa/tokenizer revision, preprocessing manifest, fitted scaler mapping for all 32 fields, graph/split run identity, checkpoint-linked validation threshold, or complete training run manifest was found. Therefore a legitimate RoBERTa NeuroGraph bundle cannot be built from currently available local evidence. No model score or performance metric was created.

### Repeatable known-review bundle command

Added `ml/reproduce_bundle.py`. For a complete future bundle, run from the repository root:

```bash
python ml/reproduce_bundle.py --manifest artifacts/bundle/run_manifest.json --manifest-sha256 "$BUNDLE_MANIFEST_SHA256"
```

The caller must set `BUNDLE_MANIFEST_SHA256` from a trusted record outside the bundle. The command requires a run manifest pointing to checksummed source dataset and license evidence, model config and checkpoint, pinned tokenizer revision, preprocessing manifest/scaler, graph with a canonical review/split identity, validation-derived threshold, saved test-prediction file, and fixed review with an expected score recorded by the originating run. It checks file hashes, rejects a declared synthetic dataset, strictly loads the checkpoint, recomputes the validation-only threshold with `ml.evaluate.find_best_threshold_on_val`, runs the graph model, and compares only the designated fixed review score within the manifest tolerance. A passing invocation would demonstrate fixed known-node reproduction only; it would not authenticate licensing or establish general performance. Batch inference/inductive support is not implied.

Attempted command:

```bash
python ml/reproduce_bundle.py --manifest artifacts/bundle/run_manifest.json --manifest-sha256 0000000000000000000000000000000000000000000000000000000000000000
```

Observed result: exit code `2`, `BUNDLE_REPRODUCTION_FAILED: run manifest is missing: artifacts/bundle/run_manifest.json`. This is the expected fail-closed outcome because no verified bundle exists. Thus the repeatability path is implemented but **a prediction was not reproduced**.

### Label-free uploaded-batch relation verification

Implemented `backend/app/services/batch_graph.py`. `load_permitted_historic_context` requires an available snapshot with explicit batch permission and selects membership for one named split. Its SQL selects only review ID, reviewer/product IDs, rating, timestamp, and text; it omits `ground_truth_label` and `label_source`. `LabelFreeBatchRelationBuilder` combines uploaded nodes and those historic context nodes using its explicitly versioned RUR/RSR/RTR definition. This verifies label-free edge construction for batch inputs in the backend test fixture, not model compatibility or production Neo4j insertion.

Executed checks:

```bash
NEO4J_URI='' python -m pytest -q backend/tests
python -m py_compile backend/app/services/batch_graph.py backend/tests/test_batch_graph.py ml/reproduce_bundle.py
```

Both commands exited `0`; pytest reported `21 passed` (with one Starlette/httpx deprecation warning). The tests verify an uploaded review links to selected history in RUR/RSR, temporal cutoff behavior for RTR, split filtering, and the executed SQL projection excludes both label columns. No Neo4j service was started or modified.
