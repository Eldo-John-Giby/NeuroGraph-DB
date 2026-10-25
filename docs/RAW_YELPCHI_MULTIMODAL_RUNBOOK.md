# Raw YelpChi multimodal benchmark runbook

## Claim and dataset boundary

This pipeline does **not** use the anonymous 45,954-node `YelpChi.mat` file.
It constructs a separate **47,176-review**, multi-relational review graph from
the fully labelled `training_data.csv` in
`samygithub/collective-opinion-spam-detection`.

`testing_data.csv` is excluded because it has no `Label` column. The raw
training labels use `Y` for spam and `N` for legitimate; the graph builder
records the explicit mapping `Y → 1`, `N → 0`. The source's star field is
`rating_OhNo`, which is used for RSR construction.

Every node is assigned by sorting the immutable raw `review ID`; the persisted
`node_identity.csv` binds its node index, raw identifiers, review text, rating,
UTC date, source split, and label. RoBERTa embeddings are computed from that
exact node ordering. This is the alignment proof.

The graph has review nodes and three directed review-to-review relation types:

- **RUR**: same reviewer ID
- **RSR**: same restaurant/product ID and rating
- **RTR**: same restaurant/product ID and UTC calendar month

This is a multi-relational homogeneous review graph. It represents the
projected R-U-R, R-S-R, and R-T-R relationships; it should not be called a
heterogeneous graph unless separate User, Product, and Time node types are
added.

## Architecture

1. `FacebookAI/roberta-base`, pinned to its resolved Hugging Face commit SHA,
   produces frozen masked-mean 768-dimensional review embeddings.
2. Fourteen label-free raw features cover rating, author/product activity,
   text statistics, and date cyclic features. The scaler is fit on train nodes
   only.
3. Three independent PyTorch Geometric `SAGEConv` layers encode RUR, RSR, and
   RTR neighbourhoods.
4. Text-conditioned relation attention weights the three structural vectors.
   A learned gate fuses the result with the text vector before classification.

The topology is transductive and known-node: all edges may be seen during
message passing; labels are restricted to train loss, validation threshold
selection, and one final test evaluation.

## Antigravity commands

Run from the repository root. Dataset downloads, graph artifacts, embedding
tensors, and model weights must stay outside Git.

```bash
python -m pip install --upgrade kaggle huggingface_hub

# Inspect the actual files before training. This must show the expected six
# identity/feature columns and exactly 47,176 labelled rows.
mkdir -p .kaggle/yelpchi-raw
kaggle datasets download -d samygithub/collective-opinion-spam-detection \
  -p .kaggle/yelpchi-raw --unzip
python - <<'PY'
import pandas as pd
from pathlib import Path
root = Path('.kaggle/yelpchi-raw')
path = next(root.rglob('training_data.csv'))
frame = pd.read_csv(path)
print('training_data.csv', len(frame), list(frame.columns))
assert len(frame) == 47176, len(frame)
assert 'Label' in frame.columns and 'rating_OhNo' in frame.columns
assert set(frame['Label'].dropna().unique()) == {'Y', 'N'}
PY

ROBERTA_SHA=$(python - <<'PY'
from huggingface_hub import HfApi
print(HfApi().model_info('FacebookAI/roberta-base').sha)
PY
)
test -n "$ROBERTA_SHA"

python ml/build_kaggle_raw_multimodal_kernel.py \
  --kaggle-username "$KAGGLE_USERNAME" \
  --text-dataset-ref "samygithub/collective-opinion-spam-detection" \
  --roberta-revision "$ROBERTA_SHA"

kaggle kernels push -p .kaggle/neurograph-raw-yelpchi-multimodal
kaggle kernels status "$KAGGLE_USERNAME/neurograph-raw-yelpchi-multimodal-gnn"
```

When Kaggle reports `complete`, retrieve and verify the bundle before recording
its run record in Git:

```bash
rm -rf /private/tmp/neurograph-raw-yelpchi-output
kaggle kernels output "$KAGGLE_USERNAME/neurograph-raw-yelpchi-multimodal-gnn" \
  -p /private/tmp/neurograph-raw-yelpchi-output

BUNDLE=$(find /private/tmp/neurograph-raw-yelpchi-output -type d -name bundle -print -quit)
MANIFEST_SHA=$(shasum -a 256 "$BUNDLE/run_manifest.json" | awk '{print $1}')
python ml/reproduce_yelpchi_multimodal_bundle.py \
  --bundle-dir "$BUNDLE" --manifest-sha256 "$MANIFEST_SHA"

cp /private/tmp/neurograph-raw-yelpchi-output/run-records/*.json docs/runs/
git add ml/ docs/RAW_YELPCHI_MULTIMODAL_RUNBOOK.md docs/runs/
git commit -m "feat(ml): add verified raw YelpChi multimodal run record"
git push origin HEAD
```

## Required defense language

Call the existing 45,954-node model **“YelpChi structured MAT GNN baseline”**.
Call a successful new run **“labelled raw YelpChi multimodal graph benchmark”**. They are
two distinct benchmarks and their metrics must not be compared as an ablation
unless a common, audited node mapping becomes available.
