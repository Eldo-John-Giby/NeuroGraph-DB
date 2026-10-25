"""Create the canonical roles and one administrator from environment variables."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from app.db import make_session_factory
from app.models import Role, User
from app.security import hash_password


def main():
    email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL")
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD")
    if not email or not password:
        raise SystemExit("Set BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD before running.")
    db = make_session_factory()()
    try:
        for key, label in (("ADMIN", "Administrator"), ("RESEARCHER", "Researcher")):
            if db.scalar(select(Role).where(Role.role_key == key)) is None:
                db.add(Role(role_key=key, display_name=label))
        db.flush()
        normalized = email.strip().lower()
        if db.scalar(select(User).where(User.email_normalized == normalized)) is None:
            role = db.scalar(select(Role).where(Role.role_key == "ADMIN"))
            db.add(User(role_id=role.role_id, email=email, email_normalized=normalized,
                        password_hash=hash_password(password)))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
