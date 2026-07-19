from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Project, User
from ..schemas import ProjectCreate, ProjectResponse
from ..security import get_current_user


router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = Project(user_id=user.id, name=payload.name.strip(), description=payload.description.strip())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectResponse])
def list_projects(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return list(db.scalars(select(Project).where(Project.user_id == user.id).order_by(Project.created_at.desc())))

