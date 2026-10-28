# Faculty demonstration route

Allow about 8 minutes. Use the live URL from README. Receive credentials privately; do not project a credential file or copy it into GitHub.

1. **Problem and ML result (one minute).** Open Model results. Explain why reviews need relational identity, durable predictions, graph context and human investigation. Distinguish ROC-AUC 0.8105 on the chronological test from accuracy on an unlabelled CSV.
2. **Researcher upload (one minute).** Sign in as the faculty/researcher. Upload the downloaded sample CSV. The compatible historical context is selected automatically; the known-node graph is intentionally ineligible for new reviews. Open saved scores and graph links.
3. **History and ownership (one minute).** Open Products & history. Search a filename, filter completed records, open the result. Reupload the same file to demonstrate receipt/run recovery without recomputation. Another researcher must not see this private history.
4. **CRUD and validation (one minute).** Open Review feedback. Use a visible review ID from Review records, create a note, search/filter it, edit its text, then remove that submitted note. It is safe to delete this disposable demonstration note; do not delete source reviews or predictions. Show invalid empty text or missing review rejection.
5. **Admin procedure and role checks (one minute).** Submit a fresh note. Sign in as administrator and triage or resolve it. The API executes PostgreSQL CALL resolve_review_feedback. A researcher receives 403 on this API and cannot edit resolved feedback. Show separate administration menus.
6. **Database design and implementation (one minute).** Open the complete ERD and dictionary. Explain users/roles, review authors/products, snapshot membership, per-run prediction keys, batch receipts and audit. Show the 0007 views, trigger and procedure. Use the PostgreSQL tests to demonstrate FK/CHECK rejection and transaction rollback.
7. **Native recovery (one minute).** Show evidence/backup-restore.json and scripts/verify_backup.py: pg_dump -Fc, isolated pg_restore, equal table counts and joined prediction provenance. Dumps remain private.
8. **Professional and bonus evidence (one minute).** Show main/dev and progressive commits, the private mirror and team invitations, the successful Actions run, Docker build, cloud HTTPS URL and test results. Explain that the default Vercel URL is not an owned custom domain and Docker Hub publication is not claimed.

For reproducible PostgreSQL-only checks, use a new empty TEST_POSTGRES_URL database. The tests refuse a database that already contains users. Do not point them at the local project database or production.
