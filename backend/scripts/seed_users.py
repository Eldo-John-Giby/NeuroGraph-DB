"""Create the default local UI accounts if they do not already exist."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db import make_session_factory
from app.models import Role, User
from app.security import hash_password


DEFAULT_USERS = (
    ("admin@neurograph.local", "Admin1234567!", "ADMIN", "Administrator"),
    ("researcher@neurograph.local", "Research1234567!", "RESEARCHER", "Researcher"),
)


def main() -> None:
    session_factory = make_session_factory()
    created: list[str] = []
    existing: list[str] = []

    with session_factory.begin() as db:
        roles: dict[str, Role] = {}
        for role_key, display_name in (("ADMIN", "Administrator"), ("RESEARCHER", "Researcher")):
            role = db.scalar(select(Role).where(Role.role_key == role_key))
            if role is None:
                role = Role(role_key=role_key, display_name=display_name)
                db.add(role)
                db.flush()
            roles[role_key] = role

        for email, password, role_key, _ in DEFAULT_USERS:
            normalized_email = email.strip().lower()
            user = db.scalar(select(User).where(User.email_normalized == normalized_email))
            if user is not None:
                existing.append(email)
                continue

            db.add(User(
                role_id=roles[role_key].role_id,
                email=email,
                email_normalized=normalized_email,
                password_hash=hash_password(password),
            ))
            created.append(email)

    for email in created:
        print(f"Created {email}")
    for email in existing:
        print(f"Already exists; left unchanged: {email}")


if __name__ == "__main__":
    main()
