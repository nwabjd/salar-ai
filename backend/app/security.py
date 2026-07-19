from datetime import datetime, timedelta, timezone
import hashlib

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .models import DeviceSession, User


password_hasher = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hasher.verify(password, hashed)


def digest_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def create_access_token(user: User, secret: str, minutes: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": user.id, "email": user.email, "iat": now, "exp": now + timedelta(minutes=minutes)},
        secret,
        algorithm="HS256",
    )


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    if credentials.credentials.startswith("sds_"):
        now = datetime.now(timezone.utc)
        session = db.scalar(
            select(DeviceSession).where(
                DeviceSession.token_hash == digest_secret(credentials.credentials),
                DeviceSession.revoked_at.is_(None),
                DeviceSession.expires_at > now,
            )
        )
        if session is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Device session is invalid or expired")
        session.last_seen_at = now
        db.commit()
        user = db.scalar(select(User).where(User.id == session.user_id))
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return user
    try:
        payload = jwt.decode(credentials.credentials, request.app.state.settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc
    user = db.scalar(select(User).where(User.id == payload.get("sub")))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
