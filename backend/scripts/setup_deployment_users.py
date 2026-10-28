"""Provision cloud demo accounts and rotate the known local demo passwords."""

import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from app.db import make_session_factory
from app.models import Role, User
from app.security import hash_password


def main():
    admin_password = os.environ["ADMIN_PASSWORD"]
    faculty_password = os.environ["FACULTY_PASSWORD"]
    if min(len(admin_password), len(faculty_password)) < 20:
        raise SystemExit("Deployment passwords must contain at least 20 characters")
    with make_session_factory().begin() as db:
        for key in ("ADMIN", "RESEARCHER"):
            if db.scalar(select(Role).where(Role.role_key == key)) is None:
                db.add(Role(role_key=key, display_name=key.title()))
        db.flush()
        accounts = (
            ("admin@neurograph.local", "ADMIN", admin_password),
            ("researcher@neurograph.local", "RESEARCHER", faculty_password),
            ("faculty@neurograph.demo", "RESEARCHER", faculty_password),
        )
        for email, role_key, password in accounts:
            role = db.scalar(select(Role).where(Role.role_key == role_key))
            user = db.scalar(select(User).where(User.email_normalized == email))
            if user is None:
                user = User(email=email, email_normalized=email, role_id=role.role_id,
                            password_hash=hash_password(password))
                db.add(user)
            else:
                user.password_hash = hash_password(password)
                user.role_id = role.role_id
                user.is_active = True
    print("Deployment admin and faculty accounts configured; known local demo passwords rotated.")


if __name__ == "__main__":
    main()
