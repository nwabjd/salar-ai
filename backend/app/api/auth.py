import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditEvent, User
from ..schemas import LoginRequest, TokenResponse, UserResponse
from ..security import create_access_token, get_current_user, verify_password


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

