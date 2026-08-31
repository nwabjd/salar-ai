import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditEvent, Project, User
from ..schemas import ProjectCreate, ProjectResponse
from ..security import get_current_user


router = APIRouter(prefix="/api/projects", tags=["projects"])


def owned_project(db: Session, user_id: str, project_id: str) -> Project:
    project = db.scalar(select(Project).where(Project.id == project_id, Project.user_id == user_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    data = payload.model_dump()
    goals = data.pop("goals", [])
    project = Project(user_id=user.id, goals_json=json.dumps(goals), **data)
    db.add(project)
    db.flush()
    db.add(AuditEvent(user_id=user.id, action="project.created", detail_json=json.dumps({"project_id": project.id})))
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Project).where(Project.user_id == user.id)
    if status_filter:
        query = query.where(Project.status == status_filter)
    if search:
        term = f"%{search}%"
        query = query.where((Project.name.ilike(term)) | (Project.description.ilike(term)))
    return list(db.scalars(query.order_by(Project.updated_at.desc().nullslast(), Project.created_at.desc())))


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return owned_project(db, user.id, project_id)


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = owned_project(db, user.id, project_id)
    data = payload.model_dump(exclude_unset=True)
    goals = data.pop("goals", None)
    if goals is not None:
        project.goals_json = json.dumps(goals)
    for key, value in data.items():
        setattr(project, key, value)
    db.add(AuditEvent(user_id=user.id, action="project.updated", detail_json=json.dumps({"project_id": project.id})))
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = owned_project(db, user.id, project_id)
    db.add(AuditEvent(user_id=user.id, action="project.deleted", detail_json=json.dumps({"project_id": project_id})))
    db.delete(project)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

