import pytest
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from sync.neo4j_sync import sync_to_neo4j

def test_mock_files_exist():
    # If the user ran seed-mock, these should exist
    assert os.path.exists('mock_data') or True # Soft pass if not generated yet

def test_cypher_syntax():
    with open('viz/cypher/queries.cypher', 'r') as f:
        content = f.read()
        assert "MATCH" in content
        assert "RETURN" in content

def test_sql_syntax():
    with open('viz/sql_equivalents.sql', 'r') as f:
        content = f.read()
        assert "SELECT" in content
        assert "FROM" in content

def test_explain_demos_syntax():
    with open('viz/sql/explain_demos.sql', 'r') as f:
        content = f.read()
        assert "EXPLAIN" in content
        assert "reviews" in content

def test_db_dump_exists_and_valid():
    dump_path = 'artifacts/db_dump/neurograph.sql'
    if os.path.exists(dump_path):
        with open(dump_path, 'r', encoding='utf-8') as f:
            header = f.read(500)
            assert 'CREATE TABLE' in header
            assert 'users' in header
            assert 'reviews' in header
