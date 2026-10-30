# Relational database design

The current application has 23 domain tables managed by SQLAlchemy and Alembic through revision `0007_database_features`.

See the [complete current ER diagram](submission/ERD.md), [field dictionary](submission/DATA_DICTIONARY.md), [normalization rationale](submission/NORMALIZATION.md) and [generated PostgreSQL schema](submission/schema-postgresql.sql).

Earlier 18-table designs are superseded. `data_pipeline/sql` and `db-dashboard/backend` belong to earlier prototypes and do not define the deployed application's schema.
