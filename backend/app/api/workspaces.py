from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Workspace
from ..security import get_current_user

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


def ensure_personal_workspace(db: Session, user_id: int) -> Workspace:
    workspace = (
        db.query(Workspace)
        .filter(Workspace.user_id == user_id, Workspace.is_default == True)
        .first()
    )
    if not workspace:
        workspace = Workspace(
            user_id=user_id,
            name="Personal",
            is_default=True,
        )
        db.add(workspace)
        db.commit()
        db.refresh(workspace)
    return workspace


@router.get("")
def list_workspaces(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_personal_workspace(db, user.id)
    return (
        db.query(Workspace)
        .filter(Workspace.user_id == user.id)
        .order_by(Workspace.is_default.desc(), Workspace.created_at.desc())
        .all()
    )


@router.post("")
def create_workspace(
    data: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_personal_workspace(db, user.id)
    workspace = Workspace(
        user_id=user.id,
        name=data.get("name", "New Workspace"),
        icon=data.get("icon"),
        color=data.get("color"),
        is_default=False,
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


@router.put("/{workspace_id}")
def update_workspace(
    workspace_id: int,
    data: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = (
        db.query(Workspace)
        .filter(Workspace.id == workspace_id, Workspace.user_id == user.id)
        .first()
    )
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if "name" in data:
        workspace.name = data["name"]
    if "icon" in data:
        workspace.icon = data["icon"]
    if "color" in data:
        workspace.color = data["color"]

    db.commit()
    db.refresh(workspace)
    return workspace


@router.delete("/{workspace_id}")
def delete_workspace(
    workspace_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = (
        db.query(Workspace)
        .filter(Workspace.id == workspace_id, Workspace.user_id == user.id)
        .first()
    )
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if workspace.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete default workspace")

    db.delete(workspace)
    db.commit()
    return {"status": "deleted"}


@router.post("/{workspace_id}/default")
def set_default_workspace(
    workspace_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = (
        db.query(Workspace)
        .filter(Workspace.id == workspace_id, Workspace.user_id == user.id)
        .first()
    )
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    db.query(Workspace).filter(
        Workspace.user_id == user.id, Workspace.is_default == True
    ).update({"is_default": False})

    workspace.is_default = True
    db.commit()
    db.refresh(workspace)
    return workspace
