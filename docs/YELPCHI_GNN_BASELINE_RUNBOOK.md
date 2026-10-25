# YelpChi 32-feature GNN baseline runbook

## Scope

This runbook produces an honest **transductive known-node** baseline for the
structured YelpChi MAT graph. It uses the 32 numeric fields and three supplied
relations: reviewer-user-review (RUR), same-rating-product-review (RSR), and
same-time-product-review (RTR). It does not use RoBERTa or claim inference for
new CSV rows, because this MAT representation has no review text or stable
mapping to rows in an uploaded CSV.

The output is a relation-aware GraphSAGE classifier, a validation-selected
threshold, a checksum manifest, and a score reproduction check for one fixed
benchmark node. The check runs without labels.

## Before the run

Use an explicit Kaggle source reference in `owner/dataset-slug` form. Do not
assume that a search result is YelpChi. The inspection script must confirm all
of these before training:

- exactly 32 feature columns
- binary labels aligned with every node
- `net_rur`, `net_rsr`, and `net_rtr` relation matrices
- no text-like field

If a text-like field is found, training stops because node-to-text alignment
requires a separate audit. If the structured contract is absent, training
stops. Record the selected source URL and its SHA-256 in `acquisition.json`.

## Local download and inspection

This keeps the raw MAT file under `backend/data/yelpchi/`; Git ignores that
directory.

```bash
python -m pip install --upgrade kaggle
export KAGGLE_YELPCHI_DATASET='OWNER/DATASET-SLUG'
python ml/kaggle_yelpchi_download.py \
  --dataset-ref "$KAGGLE_YELPCHI_DATASET" \
  --source-url "https://www.kaggle.com/datasets/$KAGGLE_YELPCHI_DATASET" \
  --expected-sha256 fedb35a8fa539b27866244d3515a47a76b20080cdacb33112da3458fd2487b42 \
  --output-dir backend/data/yelpchi
python ml/inspect_yelpchi.py \
  --mat-path backend/data/yelpchi/YelpChi.mat \
  --output backend/data/yelpchi/inspection.json
```

The dataset and acquisition record must stay local. They are evidence for the
run, not repository contents.

## Kaggle GPU run

Generate a private kernel package after inspection has selected
`structured_32_feature_gnn`.

```bash
export KAGGLE_USERNAME='YOUR_KAGGLE_ACCOUNT_SLUG'
python ml/build_kaggle_yelpchi_kernel.py \
  --kaggle-username "$KAGGLE_USERNAME" \
  --dataset-ref "$KAGGLE_YELPCHI_DATASET" \
  --output-dir .kaggle/neurograph-yelpchi-gnn-baseline
kaggle kernels push -p .kaggle/neurograph-yelpchi-gnn-baseline --accelerator NvidiaTeslaT4
kaggle kernels status "$KAGGLE_USERNAME/neurograph-yelpchi-gnn-baseline"
kaggle kernels logs "$KAGGLE_USERNAME/neurograph-yelpchi-gnn-baseline" --follow --interval 15
```

The kernel writes its output to `neurograph-yelpchi-output/`. After the status
is `complete`, download it and validate the same trusted manifest hash locally.

```bash
mkdir -p artifacts/verified_baselines/kaggle_output
kaggle kernels output "$KAGGLE_USERNAME/neurograph-yelpchi-gnn-baseline" \
  -p artifacts/verified_baselines/kaggle_output --force
BUNDLE_DIR=$(find artifacts/verified_baselines/kaggle_output -type d -name bundle | head -n 1)
MANIFEST_SHA256=$(shasum -a 256 "$BUNDLE_DIR/run_manifest.json" | awk '{print $1}')
python ml/reproduce_yelpchi_gnn_bundle.py \
  --bundle-dir "$BUNDLE_DIR" \
  --manifest-sha256 "$MANIFEST_SHA256"
```

Do not commit anything from `backend/data/` or the bundle directory. Commit the
generated small `docs/runs/<run-id>.json` record only after checking that it
contains no raw data, tokens, or checkpoint bytes.

## Result interpretation

Use the result only for the benchmark nodes and the recorded split. A fraud
score is a model probability for a known YelpChi node under this graph and
split, not proof that a real restaurant review is fake. The dashboard should
show the provenance, source hash, model type, fixed threshold, and this scope.
