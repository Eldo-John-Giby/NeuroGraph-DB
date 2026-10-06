.PHONY: all db-up schema ingest graph embed splits export validate camo-semantic camo-topology camo-build camo-validate camo-report

all: db-up schema ingest graph embed splits export validate

db-up:
	docker-compose -f docker-compose.postgres.yml up -d

schema:
	psql $$DATABASE_URL -f sql/01_schema.sql
	psql $$DATABASE_URL -f sql/02_indexes.sql

ingest:
	python scripts/02_ingest.py

graph:
	python scripts/03_build_graph.py

embed:
	python scripts/04_embed_text.py

splits:
	python scripts/05_make_splits.py

export:
	python scripts/06_export_artifacts.py

validate:
	python scripts/validate_artifacts.py

camo-semantic:
	python camouflage/semantic_attack.py

camo-topology:
	python camouflage/topology_attack.py

camo-build:
	python camouflage/build_variants.py
	pg_dump $$DATABASE_URL | gzip > ../artifacts/db_dump/neurograph.sql.gz

camo-validate:
	python camouflage/validate_variants.py

camo-report:
	python camouflage/quality_report.py\n