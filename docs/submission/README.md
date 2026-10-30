# Faculty submission evidence

This directory maps the current NeuroGraph-DB application to the Database Systems Lab rubric supplied by the team. It contains no passwords, database dumps or registration numbers. The individually addressed PDF/DOCX report and submission ZIP are prepared locally under ignored `output/submission/`.

- Live application: https://frontend-three-snowy-10.vercel.app
- Public source: https://github.com/Eldo-John-Giby/NeuroGraph-DB
- Private submission mirror: https://github.com/Avaneeshchavan/neurograph-db-submission
- [Full relational ERD](ERD.md), [data dictionary](DATA_DICTIONARY.md), [executable DDL](schema-postgresql.sql), [normalization analysis](NORMALIZATION.md).
- [Faculty demonstration route](DEMO.md) and [requirement coverage](RUBRIC.md).
- [Executed test summary](evidence/test-results.json), [native recovery drill](evidence/backup-restore.json), [actual query plan](evidence/query-plan.json).

The rubric does not specify an upload portal, filename, report template or electronic submission address. The package is prepared for the faculty; delivery through the course portal or email is not claimed. Faculty access credentials are provided separately and privately.

## Model comparison

The updated [benchmark method and results](../benchmarks/README.md) compares four architectures on the same real-data chronological split and records three training seeds. The report preserves the metric-specific outcome: concatenation has the highest mean, while the deployed NeuroGraph checkpoint has the highest seed-42 macro F1. The old synthetic near-perfect tables are excluded. Published JSON, curves, training logs and artifact manifests accompany the source.

## Evidence interpretation

The project has 23 application tables and 37 FK columns, all represented in the complete generated ERD. Do not use the older 18-table diagrams as the final schema. PostgreSQL views/procedure/trigger are installed by migration 0007. Tests use a disposable database and do not alter production predictions.

Bonus evidence covers the GitHub Actions CI pipeline and automated tests/audit logging. A provider subdomain is not presented as a custom-domain bonus. There is no configured Docker Hub account, so Docker Hub publication is not claimed. The normalized entity design includes explicitly documented physical execution/provenance redundancies; see NORMALIZATION.md for the precise boundary of the 3NF claim.

## Rebuilding the local submission

`scripts/build_submission_report.py --team <ignored private team JSON>` creates the editable report from REPORT.md, schema.json and screenshots. The authoring runtime requires python-docx and Pillow; native Arial fonts are used for the submitted rendering. The private team JSON is deliberately not committed. Render and visually inspect the DOCX/PDF before recording document-review.json. `scripts/package_submission.py` verifies the reviewed report hashes, archives committed source only and packages the deliverables without environment files or database exports.
