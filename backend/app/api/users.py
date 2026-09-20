"""
Multi-user & Workspace Sharing API.
"""
import secrets
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Workspace, WorkspaceMember, AuditEvent, token_id
from ..security import get_current_user, hash_password, require_admin

router = APIRouter(prefix="/api/users", tags=["users"])


class InviteUserRequest(BaseModel):
    email: str
    password: Optional[str] = None
    workspace_id: Optional[str] = None
    role: str = "member"


class RoleUpdateRequest(BaseModel):
    role: str


class MemberResponse(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    email: str
    role: str
    created_at: str


@router.get("/me")
def get_current_user_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owned_workspaces = list(db.scalars(select(Workspace).where(Workspace.user_id == user.id)))
    member_records = list(db.scalars(select(WorkspaceMember).where(WorkspaceMember.user_id == user.id)))
    member_ws_ids = [m.workspace_id for m in member_records]
    member_workspaces = list(db.scalars(select(Workspace).where(Workspace.id.in_(member_ws_ids)))) if member_ws_ids else []

    return {
        "id": user.id,
        "email": user.email,
        "is_admin": user.is_admin,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "owned_workspaces": [
            {"id": w.id, "name": w.name, "icon": w.icon, "color": w.color, "is_default": w.is_default}
            for w in owned_workspaces
        ],
        "shared_workspaces": [
            {"id": w.id, "name": w.name, "icon": w.icon, "color": w.color, "role": next((m.role for m in member_records if m.workspace_id == w.id), "member")}
            for w in member_workspaces
        ],
    }


@router.get("/list")
def list_users(
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    users = list(db.scalars(select(User).order_by(User.created_at.desc())))
    return {
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "is_admin": u.is_admin,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ]
    }


@router.post("/invite", status_code=status.HTTP_201_CREATED)
def invite_or_create_user(
    body: InviteUserRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    email = body.email.strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    # Inviting a user into a workspace is restricted to that workspace's owner
    # (or an admin). Creating accounts without a workspace is admin-only, so a
    # random authenticated user cannot inject themselves or spam accounts.
    ws = None
    if body.workspace_id:
        ws = db.scalar(select(Workspace).where(Workspace.id == body.workspace_id))
        if not ws:
            raise HTTPException(status_code=404, detail="Workspace not found")
        if ws.user_id != user.id and not user.is_admin:
            raise HTTPException(status_code=403, detail="You do not manage this workspace")
    elif not user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can create users without a workspace")

    target = db.scalar(select(User).where(User.email == email))
    if target is None:
        # Never seed a new account with a predictable default password. When the
        # inviter supplies no password, the user signs in via Supabase instead.
        raw_pw = body.password or secrets.token_urlsafe(24)
        target = User(
            email=email,
            password_hash=hash_password(raw_pw),
            is_admin=False,
        )
        db.add(target)
        db.flush()
        db.add(AuditEvent(user_id=user.id, action="user.created", detail_json=f'{{"created_user_id":"{target.id}"}}'))

    if ws is not None:
        existing_member = db.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == ws.id,
                WorkspaceMember.user_id == target.id,
            )
        )
        if not existing_member:
            member = WorkspaceMember(
                id=token_id(),
                workspace_id=ws.id,
                user_id=target.id,
                role=body.role,
            )
            db.add(member)

    db.commit()
    db.refresh(target)

    return {
        "status": "ok",
        "user": {
            "id": target.id,
            "email": target.email,
            "is_admin": target.is_admin,
        },
    }


@router.get("/workspaces/{workspace_id}/members")
def list_workspace_members(
    workspace_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ws = db.scalar(select(Workspace).where(Workspace.id == workspace_id))
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if ws.user_id != user.id and not user.is_admin:
        is_member = db.scalar(
            select(WorkspaceMember.id).where(
                WorkspaceMember.workspace_id == ws.id,
                WorkspaceMember.user_id == user.id,
            )
        )
        if is_member is None:
            raise HTTPException(status_code=403, detail="You do not have access to this workspace")

    members = list(
        db.execute(
            select(WorkspaceMember, User)
            .join(User, WorkspaceMember.user_id == User.id)
            .where(WorkspaceMember.workspace_id == workspace_id)
        )
    )

    result = [
        {
            "id": m.id,
            "workspace_id": m.workspace_id,
            "user_id": u.id,
            "email": u.email,
            "role": m.role,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m, u in members
    ]

    # Owner is always an implicit owner member
    owner = db.scalar(select(User).where(User.id == ws.user_id))
    if owner and not any(r["user_id"] == owner.id for r in result):
        result.insert(
            0,
            {
                "id": f"owner_{ws.id}",
                "workspace_id": ws.id,
                "user_id": owner.id,
                "email": owner.email,
                "role": "owner",
                "created_at": ws.created_at.isoformat() if ws.created_at else None,
            },
        )

    return {"members": result}


@router.delete("/workspaces/{workspace_id}/members/{member_user_id}")
def remove_workspace_member(
    workspace_id: str,
    member_user_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ws = db.scalar(select(Workspace).where(Workspace.id == workspace_id))
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if ws.user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Only the workspace owner can remove members")

    member = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == member_user_id,
        )
    )
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    db.delete(member)
    db.commit()
    return {"status": "removed"}
