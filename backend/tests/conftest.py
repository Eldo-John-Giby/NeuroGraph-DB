import os
import sys
from pathlib import Path

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-more-than-32-bytes")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ["NEO4J_URI"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import Role, User
from app.security import hash_password


@pytest.fixture()
def client():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with TestingSession() as db:
        admin_role = Role(role_key="ADMIN", display_name="Administrator")
        researcher_role = Role(role_key="RESEARCHER", display_name="Researcher")
        db.add_all([admin_role, researcher_role])
        db.flush()
        db.add(User(role_id=researcher_role.role_id, email="reader@example.edu", email_normalized="reader@example.edu", password_hash=hash_password("correct-horse-battery")))
        db.commit()

    def override_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app, base_url="https://testserver") as test_client:
        test_client._test_engine = engine
        test_client._testing_session_factory = TestingSession
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def reader_token(client):
    response = client.post("/api/v1/auth/login", json={"email": "reader@example.edu", "password": "correct-horse-battery"})
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture()
def admin_token(client):
    with client._testing_session_factory() as db:
        role = db.scalar(select(Role).where(Role.role_key == "ADMIN"))
        db.add(User(role_id=role.role_id, email="admin@example.edu", email_normalized="admin@example.edu",
                    password_hash=hash_password("admin-password-long-enough")))
        db.commit()
    response = client.post("/api/v1/auth/login", json={"email": "admin@example.edu", "password": "admin-password-long-enough"})
    assert response.status_code == 200
    return response.json()["access_token"]
