import json
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditEvent, Device, DeviceSession, User
from ..schemas import DeviceSessionResponse, DeviceSessionToken, SupabaseExchangeRequest, TokenResponse, UserResponse
from ..security import create_access_token, digest_secret, get_current_user, hash_password, verify_supabase_jwt


router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/supabase", response_model=TokenResponse)
def supabase_login(payload: SupabaseExchangeRequest, request: Request, db: Session = Depends(get_db)):
    settings = request.app.state.settings
    _sub, email = verify_supabase_jwt(payload.token, settings)
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email,
            is_admin=email in settings.admin_emails,
            password_hash=hash_password(secrets.token_urlsafe(32)),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
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


@router.get("/devices", response_model=list[DeviceSessionResponse])
def list_device_sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(DeviceSession).where(DeviceSession.user_id == user.id, DeviceSession.revoked_at.is_(None)).order_by(DeviceSession.created_at.desc())))


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_device_session(device_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    record = db.scalar(select(DeviceSession).where(DeviceSession.id == device_id, DeviceSession.user_id == user.id))
    if record is None:
        raise HTTPException(status_code=404, detail="Device session not found")
    record.revoked_at = datetime.now(timezone.utc)
    command_device = db.scalar(select(Device).where(Device.token_hash == record.token_hash))
    if command_device is not None:
        db.delete(command_device)
    db.add(AuditEvent(user_id=user.id, action="auth.device_revoked", detail_json=json.dumps({"device_id": device_id})))
    db.commit()
