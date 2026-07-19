import json
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditEvent, DeviceSession, PairingCode, User
from ..schemas import DesktopProvisionRequest, DeviceSessionResponse, DeviceSessionToken, LoginRequest, PairingCodeResponse, PairingRedeemRequest, TokenResponse, UserResponse
from ..security import create_access_token, digest_secret, get_current_user, verify_password


router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    email = payload.email.lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.password_hash):
        db.add(AuditEvent(action="auth.login_failed", detail_json=json.dumps({"email": email})))
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    db.add(AuditEvent(user_id=user.id, action="auth.login", detail_json="{}"))
    db.commit()
    return TokenResponse(
        access_token=create_access_token(user, request.app.state.settings.jwt_secret, request.app.state.settings.token_minutes)
    )


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return user


def _new_device_session(db: Session, request: Request, user: User, name: str, platform: str) -> DeviceSessionToken:
    raw = "sds_" + secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    record = DeviceSession(
        user_id=user.id,
        name=name,
        platform=platform,
        token_hash=digest_secret(raw),
        expires_at=now + timedelta(days=request.app.state.settings.device_session_days),
        last_seen_at=now,
    )
    db.add(record)
    db.flush()
    device = DeviceSessionResponse.model_validate(record, from_attributes=True)
    return DeviceSessionToken(access_token=raw, device=device)


def _code_digest(code: str, secret: str) -> str:
    return hashlib.sha256(f"{secret}:{code}".encode()).hexdigest()


@router.post("/desktop/provision", response_model=DeviceSessionToken, status_code=status.HTTP_201_CREATED)
def provision_desktop(payload: DesktopProvisionRequest, request: Request, db: Session = Depends(get_db)):
    settings = request.app.state.settings
    if not secrets.compare_digest(payload.provisioning_key, settings.provisioning_key):
        db.add(AuditEvent(action="auth.provision_rejected", detail_json=json.dumps({"name": payload.name})))
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid provisioning key")
    user = db.scalar(select(User).where(User.email == settings.bootstrap_email.lower()))
    if user is None:
        raise HTTPException(status_code=503, detail="Owner account is unavailable")
    result = _new_device_session(db, request, user, payload.name, "windows")
    db.add(AuditEvent(user_id=user.id, action="auth.desktop_provisioned", detail_json=json.dumps({"name": payload.name})))
    db.commit()
    return result


@router.get("/session", response_model=UserResponse)
def validate_session(user: User = Depends(get_current_user)):
    return user


@router.post("/pairing", response_model=PairingCodeResponse, status_code=status.HTTP_201_CREATED)
def create_pairing(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=request.app.state.settings.pairing_code_minutes)
    db.add(PairingCode(user_id=user.id, code_hash=_code_digest(code, request.app.state.settings.jwt_secret), expires_at=expires_at))
    db.add(AuditEvent(user_id=user.id, action="auth.pairing_created", detail_json="{}"))
    db.commit()
    return PairingCodeResponse(code=code, expires_at=expires_at)


@router.post("/pairing/redeem", response_model=DeviceSessionToken, status_code=status.HTTP_201_CREATED)
def redeem_pairing(payload: PairingRedeemRequest, request: Request, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    record = db.scalar(select(PairingCode).where(PairingCode.code_hash == _code_digest(payload.code, request.app.state.settings.jwt_secret)))
    if record is None:
        raise HTTPException(status_code=404, detail="Pairing code was not found")
    if record.redeemed_at is not None:
        raise HTTPException(status_code=409, detail="Pairing code has already been used")
    expires = record.expires_at if record.expires_at.tzinfo else record.expires_at.replace(tzinfo=timezone.utc)
    if expires <= now:
        raise HTTPException(status_code=410, detail="Pairing code has expired")
    user = db.scalar(select(User).where(User.id == record.user_id))
    if user is None:
        raise HTTPException(status_code=404, detail="Owner account was not found")
    record.redeemed_at = now
    result = _new_device_session(db, request, user, payload.name, payload.platform)
    db.add(AuditEvent(user_id=user.id, action="auth.pairing_redeemed", detail_json=json.dumps({"name": payload.name})))
    db.commit()
    return result


@router.get("/devices", response_model=list[DeviceSessionResponse])
def list_device_sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(DeviceSession).where(DeviceSession.user_id == user.id, DeviceSession.revoked_at.is_(None)).order_by(DeviceSession.created_at.desc())))


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_device_session(device_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    record = db.scalar(select(DeviceSession).where(DeviceSession.id == device_id, DeviceSession.user_id == user.id))
    if record is None:
        raise HTTPException(status_code=404, detail="Device session not found")
    record.revoked_at = datetime.now(timezone.utc)
    db.add(AuditEvent(user_id=user.id, action="auth.device_revoked", detail_json=json.dumps({"device_id": device_id})))
    db.commit()
