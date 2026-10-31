# NeuroGraph frontend

Next.js 15.5, React 18 and TypeScript implement the authenticated review workspace. The production site is hosted on Vercel Hobby and proxies API requests to FastAPI on AWS.

## Local development

```sh
npm ci
cp .env.example .env.local
npm run dev
```

Set `BACKEND_URL` to your API origin. It is a server-side proxy setting; database passwords, signing secrets and deployment tokens must never be copied here. Local development defaults to `http://localhost:8000`.

## Pages

- `/`: deployed model result, evidence and recent analyses.
- `/benchmarks`: four matched model arms on the same test set, selectable seed/mean, metric charts, ROC/PR curves, missing-context sensitivity and all three historical records.
- `/reviews/submit`: CSV upload and scoring.
- `/products`: current user's saved upload history; admins can explicitly select all users.
- `/products/[batchId]`: plain-English saved result summary; row filters/search/pagination; complete CSV export; full-text review dialog, recorded context and direct feedback link.
- `/feedback`: human notes and administrator moderation.
- `/reviews`: accessible review records.
- `/examples`: labelled synthetic investigations.
- `/models`, `/admin/users`, `/admin/audit`: admin UI for registry, accounts and diagnostics.
- `/reviewers`: administrator source-author lookup with full-catalog pagination, clearly page-scoped filtering and working author-to-review navigation. No account-level fraud scores are assigned.

`public/benchmarks/comparison.json` is generated from verified training records by `scripts/publish_benchmark.py`; performance numbers are not handwritten into charts. It is a recorded evaluation, not a live training job. Historical experiments have different protocols and are displayed outside the matched ranking.

## Validation and deployment

```sh
node --test tests/*.test.cjs
npm run lint
npm run build
```

Use the root `scripts/deploy_frontend.py` with the existing backend HTTPS origin for a checked CLI deployment. See [deployment details](../../deploy/aws/README.md) and the [root guide](../../README.md).

The model registry is read-only provenance and current inductive-runtime status. Benchmark comparisons are kept on `/benchmarks`; historical known-node runtime banners do not stand in for current upload availability. Frontend tests cover saved-decision counting, missing-score handling, filtering/order and formula-safe complete CSV export as well as session refresh.
