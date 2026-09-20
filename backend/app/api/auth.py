import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditEvent, User
from ..rate_limit import limiter
from ..schemas import LoginRequest, SupabaseExchangeRequest, TokenResponse, UserResponse
from ..security import create_access_token, get_current_user, hash_password, verify_password, verify_supabase_jwt


router = APIRouter(prefix="/api/auth", tags=["authentication"])

SOLE_ADMIN_EMAIL = "nwabjd@gmail.com"


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.strip().lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    db.add(AuditEvent(user_id=user.id, action="auth.login", detail_json="{}"))
    db.commit()
    return TokenResponse(
        access_token=create_access_token(user, request.app.state.settings.jwt_secret, request.app.state.settings.token_minutes)
    )


@router.post("/supabase", response_model=TokenResponse)
@limiter.limit("5/minute")
def supabase_login(payload: SupabaseExchangeRequest, request: Request, db: Session = Depends(get_db)):
    settings = request.app.state.settings
    _sub, email = verify_supabase_jwt(payload.token, settings)
    admin_set = {e.strip().lower() for e in (settings.admin_emails or [])}
    is_admin = email.strip().lower() == SOLE_ADMIN_EMAIL or email.strip().lower() in admin_set
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email,
            is_admin=is_admin,
            password_hash=hash_password(secrets.token_urlsafe(32)),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif user.is_admin != is_admin:
        user.is_admin = is_admin
        db.commit()
    db.add(AuditEvent(user_id=user.id, action="auth.supabase_login", detail_json="{}"))
    db.commit()
    return TokenResponse(
        access_token=create_access_token(user, settings.jwt_secret, settings.token_minutes)
    )


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return user


@router.get("/session", response_model=UserResponse)
def validate_session(user: User = Depends(get_current_user)):
    return user
