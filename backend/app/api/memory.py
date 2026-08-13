import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditEvent, Memory, User
from ..schemas import MemoryCreate, MemoryResponse
from ..security import get_current_user


router = APIRouter(prefix="/api/memories", tags=["memory"])


def owned_memory(db: Session, user_id: str, memory_id: str) -> Memory:
    memory = db.scalar(select(Memory).where(Memory.id == memory_id, Memory.user_id == user_id))
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory


@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
def create_memory(payload: MemoryCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    memory = Memory(user_id=user.id, **payload.model_dump())
    db.add(memory)
    db.flush()
    db.add(AuditEvent(user_id=user.id, action="memory.created", detail_json=json.dumps({"memory_id": memory.id})))
    db.commit()
    db.refresh(memory)
    return memory


@router.get("", response_model=list[MemoryResponse])
def list_memories(
    layer: Optional[str] = None,
    kind: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Memory).where(Memory.user_id == user.id)
    if layer:
        query = query.where(Memory.layer == layer)
    if kind:
        query = query.where(Memory.kind == kind)
    return list(db.scalars(query.order_by(Memory.updated_at.desc())))


@router.patch("/{memory_id}", response_model=MemoryResponse)
def update_memory(
    memory_id: str,
    payload: MemoryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    memory = owned_memory(db, user.id, memory_id)
    for key, value in payload.model_dump().items():
        setattr(memory, key, value)
    db.add(AuditEvent(user_id=user.id, action="memory.updated", detail_json=json.dumps({"memory_id": memory.id})))
    db.commit()
    db.refresh(memory)
    return memory


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(
    memory_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    memory = owned_memory(db, user.id, memory_id)
    db.delete(memory)
    db.add(AuditEvent(user_id=user.id, action="memory.deleted", detail_json=json.dumps({"memory_id": memory_id})))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

