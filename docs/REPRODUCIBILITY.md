# Reproduction guide

The [root README](../README.md) covers environment setup and database/API/UI tests. The [model comparison method](benchmarks/README.md) records the shared data/split fingerprints, model definitions, fixed training controls and all run artifacts.

## Scientific reproduction

Acquire the labelled raw CSV identified in the model card and the exact verified inductive bundle. Large model files are distributed separately from Git. The bundle contains the cached frozen RoBERTa embeddings, scaled metadata, causal graph and evaluation targets. The benchmark verifies their fingerprints before use.

```sh
docker build -t neurograph-api:deploy -f backend/Dockerfile .
docker build -t neurograph-benchmark:local -f ml/Dockerfile.benchmark .
mkdir -p artifacts/matched_benchmark/temporal_v1
docker run --rm --network none --cpus 6 --memory 5g \
  -v "$PWD:/repo:ro" \
  -v "$PWD/artifacts/matched_benchmark/temporal_v1:/results" \
  -w /repo -e PYTHONPATH=/repo:/repo/backend \
  neurograph-benchmark:local python ml/benchmark_matched.py --output /results
python3 scripts/publish_benchmark.py
```

The output directory stores the protocol before training, then per-run checkpoint/selection/log/prediction/manifest files. Resume refuses a changed protocol or training source. NeuroGraph seed 42 reuses the original sealed checkpoint rather than selecting a new checkpoint based on known test results. Seeds 43/44 and all baselines are trained under the fixed plan. Sparse CSR propagation is checked against ordinary graph propagation and the deployed checkpoint's metrics.

## Application and recovery

```sh
cd backend
PYTHONPATH=..:. pytest
cd ../db-dashboard/frontend
node --test tests/auth-refresh.test.cjs
npm run lint
npm run build
```

Use an empty disposable `TEST_POSTGRES_URL` for PostgreSQL-only tests; never a live project database. `scripts/verify_backup.py` performs a native isolated dump/restore drill. Existing execution records are in `docs/submission/evidence` and must be identified by date rather than presented as a fresh run.

The recorded comparison does not require new cloud resources. See [deployment](../deploy/aws/README.md) for guarded terminal operations. No private credentials or model artifacts belong in frontend environment variables.
