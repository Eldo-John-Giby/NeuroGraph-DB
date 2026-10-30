# Database field dictionary

Use the [complete generated dictionary](submission/DATA_DICTIONARY.md) for all 23 current application tables, field types, primary and foreign keys, constraints, indexes and delete rules.

The [schema export](submission/schema.json) comes from the SQLAlchemy models and is checked against the Alembic migrations. Review authors live in `reviewers`; website accounts live in `users`. Model predictions, human feedback and source labels are separate records.
