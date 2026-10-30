# YelpChi multimodal training runbook

**Scope:** an earlier proposed raw-text/MAT alignment route, not the source of the three reported real-data experiments. The executed raw model uses its own 47,176-row graph; see [the raw runbook](RAW_YELPCHI_MULTIMODAL_RUNBOOK.md). For the current comparable results use [the matched benchmark](benchmarks/README.md).

## Hard gate: verify identity before training

`YelpChi.mat` in the verified GNN bundle has 45,954 nodes. The raw-text corpus
reported for YelpChi has 67,395 reviews. The MAT file has no review ID,
reviewer ID, product ID, or text field. A shared dataset name, row ordering, or
matching labels does not establish a join.

Run `ml/verify_yelpchi_text_alignment.py` first. It trains only if an
**authoritative** `node_index_map.csv` exists, produced by the graph builder
that created the exact MAT file. Its required columns are:

```text
node_index,review_id,reviewer_id,product_id,label
```

The validator requires a bijection over `0..45953`, exact label agreement with
the MAT file, and an exact one-to-one join against the combined CSVs. It rejects
the current inputs when that map is absent. This is deliberate: silently
assuming CSV row *i* belongs to MAT node *i* would contaminate every split and
invalidate the result.

If the index map cannot be obtained, build a **new** 67,395-node graph from the
raw CSV and call it a separate raw-text YelpChi benchmark. First inspect whether
the CSV actually provides timestamp and rating columns. Both are required to
derive RSR and RTR honestly; review/user/product IDs alone only support RUR.
Do not describe a new graph as the 45,954-node MAT graph.

## Model and leakage protocol

The trainer uses an immutable, frozen `FacebookAI/roberta-base` revision.
Masked-mean pooled 768-dimensional text embeddings are generated once, then
combined with train-fitted standardized 32-feature metadata.

Each RUR, RSR, and RTR adjacency is passed through its own PyTorch Geometric
`SAGEConv`. The text embedding is the query over three relation-specific
structural embeddings; softmax relation attention yields a graph vector. A
learned gate fuses it with the text vector before binary classification. The
stored attention vector is evidence of which relation informed a prediction; it
is not a causal explanation.

The deterministic 60/20/20 stratified node split is created before fitting the
metadata scaler. Labels are used only for train loss, validation threshold
selection, and the single final test evaluation. Full topology remains visible
during message passing because this is explicitly a transductive known-node
benchmark. No test label is supplied to the reproduction program.

## Antigravity: prepare the Kaggle inputs

Run these from the repository root. The first two downloads are inspection only;
do not add downloaded data to Git.

```bash
mkdir -p .kaggle/yelpchi-raw
kaggle datasets download -d samygithub/collective-opinion-spam-detection -p .kaggle/yelpchi-raw --unzip
python - <<'PY'
import pandas as pd
from pathlib import Path
for name in ("training_data.csv", "testing_data.csv"):
    path = next(Path(".kaggle/yelpchi-raw").rglob(name))
    frame = pd.read_csv(path, nrows=3)
    print(name, "columns=", list(frame.columns))
    print("rows=", sum(1 for _ in path.open(encoding="utf-8", errors="replace")) - 1)
PY
```

Create a private Kaggle dataset that contains an authoritative
`node_index_map.csv` **only after its lineage is documented**. It must be
attached in addition to the MAT and raw-text datasets. The current text dataset
does not itself provide this missing mapping.

## Antigravity: build and submit the GPU kernel

Use the same structured graph dataset ref that produced the verified baseline.
Resolve the actual Hugging Face commit at submission time; never use `main` or a
tag as the training revision.

```bash
python -m pip install --upgrade huggingface_hub kaggle
ROBERTA_SHA=$(python - <<'PY'
from huggingface_hub import HfApi
print(HfApi().model_info("FacebookAI/roberta-base").sha)
PY
)
test -n "$ROBERTA_SHA"

python ml/build_kaggle_multimodal_kernel.py \
  --kaggle-username "$KAGGLE_USERNAME" \
  --graph-dataset-ref "zhouxuanmingchen/yelp-fraud-processed" \
  --text-dataset-ref "samygithub/collective-opinion-spam-detection" \
  --index-map-dataset-ref "YOUR_KAGGLE_USERNAME/yelpchi-mat-node-index-map" \
  --roberta-revision "$ROBERTA_SHA"

kaggle kernels push -p .kaggle/neurograph-yelpchi-multimodal
kaggle kernels status "$KAGGLE_USERNAME/neurograph-yelpchi-multimodal"
```

The generated runner validates alignment before it installs or downloads the
RoBERTa model. A kernel failure marked `ALIGNMENT_NOT_VERIFIED` is a correct
result: supply the authoritative map or stop the MAT fusion claim.

After Kaggle reports `complete`:

```bash
rm -rf /private/tmp/neurograph-yelpchi-multimodal-output
kaggle kernels output "$KAGGLE_USERNAME/neurograph-yelpchi-multimodal" \
  -p /private/tmp/neurograph-yelpchi-multimodal-output

BUNDLE=$(find /private/tmp/neurograph-yelpchi-multimodal-output -type d -name bundle -print -quit)
MANIFEST_SHA=$(shasum -a 256 "$BUNDLE/run_manifest.json" | awk '{print $1}')
python ml/reproduce_yelpchi_multimodal_bundle.py \
  --bundle-dir "$BUNDLE" --manifest-sha256 "$MANIFEST_SHA"

cp /private/tmp/neurograph-yelpchi-multimodal-output/run-records/*.json docs/runs/
git add ml/ docs/YELPCHI_MULTIMODAL_RUNBOOK.md docs/runs/
git commit -m "feat(ml): add verified YelpChi multimodal run record"
git push origin HEAD
```

Raw datasets, index maps containing source text, RoBERTa embedding tensors, and
PyTorch weights remain outside Git. Preserve the downloaded bundle separately
and register it in the application only after its reproduction command passes.
