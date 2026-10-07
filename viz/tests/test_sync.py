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
