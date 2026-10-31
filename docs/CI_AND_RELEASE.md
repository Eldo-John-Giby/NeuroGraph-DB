# GitHub Actions and release evidence

## What the custom workflow does

The repository's `.github/workflows/ci.yml` is configured for this application's stack, rather than an unused template. A code push or pull request targeting `main` or `dev` starts three independent jobs. Documentation-only changes are excluded; the workflow can also be started manually.

| Job | Actual automated work | Why it matters |
|---|---|---|
| Backend | Install CPU ML/API dependencies, create disposable PostgreSQL 16, run FastAPI/model/auth/ownership and real database migration/procedure/trigger tests, then scientific benchmark-contract checks | Finds broken API behavior, access checks, schema/database features and model-evidence contracts |
| Frontend | Clean npm install, authentication and result-interpretation/export regression tests, lint, TypeScript/Next production build and dependency audit | Catches broken UI builds, session recovery regressions and misleading result/export behavior |
| Container | Build the deployable backend Docker image and import the actual FastAPI app inside it | Checks that the packaged service can load |

A red required job means that job failed. A green run means those automated checks passed for that source revision; it does not prove every UI or future prediction is correct. Scientific tests in a clean checkout explicitly skip private-bundle-dependent reproduction when the large artifacts are absent. Local artifact-backed reproduction evidence is recorded separately.

The public repository uses standard Linux GitHub-hosted runners. Private-mirror jobs intentionally skip to avoid metered private CI usage. Actions receive read-only repository contents access. No production AWS credentials, production database connection or deployment tokens are embedded in the workflow.

## What is and is not automatic

This is implemented **continuous integration (CI)**. It tests and builds commits automatically. It does **not** automatically deploy the frontend/backend after a green run, publish Docker Hub images, retrain the live model or replace production weights. Production release currently uses explicit Vercel CLI and the guarded AWS/SSM deployment scripts. Do not describe this as automatic continuous deployment (CD) or a CI-enforced deployment gate.

An explicit release is checked and verified separately. Backend scripts require the expected AWS account, Free/Active plan, expiry and credit reserve before mutations. The hosting allowance is finite; no paid upgrade or indefinitely free hosting is promised.

## How to show the faculty

1. Open the repository's **Actions → Verified application CI** and select a successful run on the submitted commit. The completed jobs and their step logs are the evidence.
2. Show `.github/workflows/ci.yml`: the triggers, PostgreSQL service, actual test commands, frontend build and container build.
3. Explain: “When we change application code, GitHub runs our tests and builds on a fresh machine. If a check fails, we get a failed run to fix before releasing. Deployment is a separate explicit step.”
4. For database evidence, open the backend job's PostgreSQL tests and then the actual procedure/trigger tests. A build-only workflow would not demonstrate these checks.

The verified full run for the final application code is https://github.com/Eldo-John-Giby/NeuroGraph-DB/actions/runs/41171173940 (commit `6b5c742f8887f89239b3d1ec8241e4b1456315b0`). Use the newer submitted revision's successful run when available; do not imply an older run tested later code.

## Bonus mapping

The supplied handout's bonus table names “CI/CD Pipeline using GitHub Actions or GitLab CI/CD” for **+1**. The implemented CI pipeline is substantive evidence to present for that category; final interpretation and award belong to the faculty. We claim implemented CI, not unimplemented automatic CD.

Automated testing, audited feedback changes, native restore verification and measured query-plan evidence additionally support the **one** industry-practice +1 category. These are not several separate bonus marks. The project does not claim the +1 custom-domain category: Vercel and sslip.io are provider hostnames, not a separately configured owned domain. See `submission/RUBRIC.md` for all qualifications.
