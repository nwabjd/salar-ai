# backend/app/api/memory_graph.py
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Memory, MemoryRelation, User
from ..security import get_current_user
from ..services.memory_graph import MEMORY_KINDS, MemoryGraph

router = APIRouter(prefix="/api/memory-graph", tags=["memory-graph"])


class ConnectBody(BaseModel):
    to_memory_id: str
    relation: str = "related"


def _owned(db: Session, user_id: str, memory_id: str) -> Memory:
    memory = db.get(Memory, memory_id)
    if memory is None or memory.user_id != user_id:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory


@router.get("")
def graph(limit: int = 200, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return MemoryGraph(db).graph(user.id, limit_nodes=limit)


@router.get("/{memory_id}/neighbors")
def neighbors(
    memory_id: str,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _owned(db, user.id, memory_id)
    return MemoryGraph(db).neighbors(user.id, memory_id, limit=limit)


@router.post("/{memory_id}/connect")
def connect(
    memory_id: str,
    body: ConnectBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _owned(db, user.id, memory_id)
    _owned(db, user.id, body.to_memory_id)
    try:
        rel = MemoryGraph(db).connect(user.id, memory_id, body.to_memory_id, body.relation)
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    try:
        from ..services.world_model import MemorySyncService
        MemorySyncService(db).sync_relations(user.id)
        db.commit()
    except Exception:
        db.rollback()
    return {"id": rel.id, "from": memory_id, "to": body.to_memory_id, "relation": rel.relation}


@router.delete("/relations/{relation_id}")
def disconnect(relation_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not MemoryGraph(db).disconnect(user.id, relation_id):
        raise HTTPException(status_code=404, detail="Relation not found")
    db.commit()
    return {"status": "disconnected"}
