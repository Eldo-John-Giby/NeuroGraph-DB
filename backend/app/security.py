import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import SessionToken, User

password_hasher = PasswordHasher()
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters")
    return password_hasher.hash(password)


def verify_password(encoded: str, password: str) -> bool:
    try:
        return password_hasher.verify(encoded, password)
    except (VerifyMismatchError, VerificationError, ValueError):
        return False


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def issue_session(db: Session, user: User) -> tuple[SessionToken, str, str]:
    settings = get_settings()
    if not settings.configured_jwt_secret:
        raise HTTPException(status_code=503, detail={"code": "auth_not_configured", "message": "JWT_SECRET_KEY must contain at least 32 characters."})
    now = datetime.now(timezone.utc)
    access_exp = now + timedelta(minutes=settings.access_token_minutes)
    refresh_exp = now + timedelta(days=settings.refresh_token_days)
    jti = secrets.token_urlsafe(24)
    refresh = secrets.token_urlsafe(48)
    session = SessionToken(
        user_id=user.user_id,
        access_jti_hash=digest(jti),
        refresh_token_hash=digest(refresh),
        access_expires_at=access_exp,
        refresh_expires_at=refresh_exp,
    )
    db.add(session)
    db.flush()
    token = jwt.encode({"sub": str(user.user_id), "sid": session.session_token_id, "jti": jti, "iat": now, "exp": access_exp}, settings.jwt_secret_key, algorithm="HS256")
    return session, token, refresh


def current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail={"code": "unauthenticated", "message": "Bearer access token required."}, headers={"WWW-Authenticate": "Bearer"})
    settings = get_settings()
    if not settings.configured_jwt_secret:
        raise HTTPException(status_code=503, detail={"code": "auth_not_configured", "message": "Authentication is not configured."})
    try:
        claims = jwt.decode(credentials.credentials, settings.jwt_secret_key, algorithms=["HS256"])
        user_id = int(claims["sub"])
        session_id = claims["sid"]
        jti = claims["jti"]
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail={"code": "invalid_token", "message": "Access token is invalid or expired."}, headers={"WWW-Authenticate": "Bearer"})
    session = db.get(SessionToken, session_id)
    now = datetime.now(timezone.utc)
    if session is None or session.user_id != user_id or session.revoked_at is not None or session.access_jti_hash != digest(jti) or as_utc(session.access_expires_at) <= now:
        raise HTTPException(status_code=401, detail={"code": "revoked_session", "message": "Session is expired or revoked."}, headers={"WWW-Authenticate": "Bearer"})
    user = db.scalar(select(User).where(User.user_id == user_id, User.is_active.is_(True)))
    if user is None:
        raise HTTPException(status_code=401, detail={"code": "inactive_account", "message": "Account is inactive."})
    request.state.user_id = user.user_id
    return user


def require_roles(*role_keys: str):
    def dependency(user: User = Depends(current_user), db: Session = Depends(get_db)) -> User:
        from app.models import Role
        role = db.get(Role, user.role_id)
        if role is None or role.role_key not in role_keys:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "forbidden", "message": "Required role is missing."})
        return user
    return dependency
