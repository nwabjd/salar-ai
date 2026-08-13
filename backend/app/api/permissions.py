# backend/app/api/permissions.py
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import PermissionProfile as PermissionProfileModel, User, token_id, utcnow
from ..security import get_current_user
from ..services.permissions import (
    CATEGORIES,
    PermissionProfile,
    valid_level,
)

router = APIRouter(prefix="/api/permissions", tags=["permissions"])


class UpdateBody(BaseModel):
    category: str
    level: str


@router.get("")
def get_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = PermissionProfile.for_user(db, current_user.id)
    return {
        "categories": {cat: profile.level_for(cat) for cat in CATEGORIES},
        "default": "ask",
    }


@router.put("")
def update_permissions(
    body: UpdateBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.category not in CATEGORIES:
        raise HTTPException(status_code=400, detail=f"unknown category: {body.category}")
    if not valid_level(body.level):
        raise HTTPException(status_code=400, detail=f"invalid level: {body.level}")

    row = db.query(PermissionProfileModel).filter(PermissionProfileModel.user_id == current_user.id).first()
    if row is None:
        profile = PermissionProfile(user_id=current_user.id)
        row = PermissionProfileModel(
            id=token_id(), user_id=current_user.id, levels_json=profile._to_json(),
            created_at=utcnow(), updated_at=utcnow(),
        )
        db.add(row)
        db.flush()
    levels = row.levels_dict()
    levels[body.category] = body.level
    row.levels_json = json.dumps(levels)
    row.updated_at = utcnow()
    db.commit()
    db.refresh(row)
    updated = PermissionProfile.for_user(db, current_user.id)
    return {"categories": {cat: updated.level_for(cat) for cat in CATEGORIES}}
