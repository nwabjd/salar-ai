from datetime import datetime, timedelta, timezone
import logging

import jwt
from jwt import PyJWKClient
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .models import User


password_hasher = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)

logger = logging.getLogger("salar.security")

_jwks_clients = {}


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hasher.verify(password, hashed)


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
    try:
        payload = jwt.decode(credentials.credentials, request.app.state.settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc
    user = db.scalar(select(User).where(User.id == payload.get("sub")))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Resolve the authenticated user or return None (no 401)."""
    if credentials is None:
        return None
    try:
        return get_current_user(request, credentials, db)
    except HTTPException:
        return None


def verify_supabase_jwt(token: str, settings) -> tuple[str, str]:
    """Return (sub, email) for a valid Supabase access token, else raise 401.

    Supports both signing modes Supabase issues:
    - HS256 tokens signed with the project JWT secret (legacy anon/service keys).
    - ES256 (and RS256) tokens signed with the project's JWKS key, which is the
      default for access tokens on current projects.
    """
    if not settings.supabase_url:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Supabase is not configured")
    try:
        alg = jwt.get_unverified_header(token).get("alg")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    issuer = f"{settings.supabase_url.rstrip('/')}/auth/v1"
    try:
        if alg == "HS256":
            if not settings.supabase_jwt_secret:
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Supabase is not configured")
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience=settings.supabase_audience,
                issuer=issuer,
                options={"require": ["exp", "sub", "email"]},
            )
        elif alg in ("ES256", "RS256"):
            jwks_url = f"{issuer}/.well-known/jwks.json"
            signing_key = _jwks_clients.setdefault(jwks_url, PyJWKClient(jwks_url, cache_keys=True)).get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=[alg],
                audience=settings.supabase_audience,
                issuer=issuer,
                options={"require": ["exp", "sub", "email"]},
            )
        else:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unsupported token algorithm")
    except jwt.PyJWTError as exc:
        logger.warning("supabase token verification failed for alg=%s: %s", alg, exc)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return str(payload["sub"]), str(payload["email"]).lower()


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
