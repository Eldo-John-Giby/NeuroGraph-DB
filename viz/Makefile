.PHONY: neo4j-up seed-mock sync sync-variant app explain test

neo4j-up:
	docker-compose -f docker-compose.neo4j.yml up -d

seed-mock:
	python mock/seed_mock.py

sync:
	python sync/neo4j_sync.py

sync-variant:
	python sync/neo4j_sync.py --variant $(VARIANT) --subgraph

app:
	streamlit run app/streamlit_app.py

explain:
	python sql/run_explain.py

test:
	pytest tests/
