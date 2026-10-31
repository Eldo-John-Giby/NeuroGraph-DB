# Rubric coverage and evidence

The supplied handout allocates 30 base marks and up to 3 bonus marks. This is evidence mapping, not a prediction or guarantee of awarded marks.

| Section | Marks | Demonstrable implementation and evidence | Remaining qualification |
|---|---:|---|---|
| Problem and planning | 2 | Report: problem, objectives, scope, named responsibilities, stack, deliverables and dated Gantt; Git history beginning 6 October 2026 | Faculty domain approval is a course decision; no approval is invented |
| Database design | 6 | 23 tables; 37 FK columns; all PKs; complete ERD, relational schema and dictionary; normalization analysis | Core entities are normalized; physical provenance classifications intentionally repeat linked model/run values and are explicitly disclosed |
| Database implementation | 8 | PostgreSQL 16; SQLAlchemy CRUD, joins, bound searches, grouped aggregates; 2 views; transactions; procedure and trigger; indexes; Alembic DDL; real PostgreSQL regression tests | Raw SQL is limited to migration DDL, native diagnostics, and CALL |
| Application development | 4 | Next.js/FastAPI, responsive dashboard, CSV validation, saved history, search/status filters/pagination, complete feedback CRUD, structured exceptions | ML bundles are separately distributed; a fresh clone cannot score until verified bundles are installed |
| Authentication and security | 5 | ADMIN/RESEARCHER in one users table with roles FK; Argon2; JWT; rotating refresh cookies; logout/revocation; ORM/API and menu/page RBAC; private data scoping; restricted CORS; ignored secrets | The deployment DB owner is privileged; least-privilege DB roles are a future production hardening item |
| Professional practices | 5 | Progressive history >10 commits; main/dev branches; existing team collaboration and private mirror; ignored sensitive files; native restore drill; Docker image and cloud HTTPS deployment | Private mirror collaborator invitations require acceptance; Docker Hub publication needs a Docker Hub account |
| CI pipeline bonus | +1 candidate | .github/workflows/ci.yml tests FastAPI, real PostgreSQL, Next.js/auth and builds Docker on public source commits | Implemented CI; production CLI release is separate, not automatic CD. Show the successful run for the submitted commit; private mirror hosted jobs intentionally skip |
| Custom domain bonus | +1 not claimed | Vercel and sslip.io provider hostnames provide public HTTPS | No owned/registered custom domain is configured; no domain purchase is made |
| Additional practice bonus | +1 candidate | Executed automated tests, PostgreSQL audit trigger, redacted logs, provenance checks, restore verification, EXPLAIN evidence | Several practices support one bonus category; they are not counted as multiple extra marks |

## Controls relevant to database evaluation

- Keep login identities in users; external reviewers are source identities, not a second login table.
- Researcher history defaults to the requester, including after duplicate canonical review reuse.
- Joins attach saved predictions to run/model/preprocessing/graph identity; uploaded labels cannot establish accuracy.
- Use feedback CRUD to demonstrate create/read/update/delete without deleting immutable model evidence.
- Procedure resolution does not change original labels, model scores or trained weights.
- Trigger audit data includes allowlisted status/type/label/review IDs, excluding passwords, tokens and free-text comments.
- The restore script creates a new disposable database and never restores over the running source.

See [CI and release explanation](../CI_AND_RELEASE.md) for the exact automated steps, successful run evidence and the distinction between CI and automatic CD.
