# backend/app/api/deep_research.py
import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DeepResearch, User
from ..security import get_current_user
from ..services.deep_research import DeepResearchError, DeepResearchMode

router = APIRouter(prefix="/api/research", tags=["research"])


class ResearchBody(BaseModel):
    goal: str


def _serialize(row: DeepResearch) -> dict:
    return {
        "id": row.id,
        "goal": row.goal,
        "status": row.status,
        "error": row.error,
        "agents": json.loads(row.agents_json or "[]"),
        "synthesis": json.loads(row.synthesis_json or "{}"),
        "findings": json.loads(row.findings_json or "[]"),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.post("", status_code=status.HTTP_200_OK)
async def start_research(
    body: ResearchBody,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    goal = body.goal.strip()
    if not goal:
        raise HTTPException(status_code=422, detail="Goal cannot be empty")

    coordinator = getattr(request.app.state, "coordinator", None)
    gemini = getattr(coordinator, "gemini", None) if coordinator else None
    if gemini is None:
        raise HTTPException(status_code=503, detail="Gemini client not configured")

    row = DeepResearch(
        user_id=user.id, goal=goal, status="running",
        agents_json="[]", synthesis_json="{}", findings_json="[]",
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    try:
        result = await DeepResearchMode(gemini=gemini).run(goal)
        stored = DeepResearchMode().store(db, user.id, result)
    except DeepResearchError as exc:
        row.status = "failed"
        row.error = str(exc)
        db.commit()
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        row.status = "failed"
        row.error = f"{type(exc).__name__}: {exc}"
        db.commit()
        raise HTTPException(status_code=500, detail="Research failed")
    return _serialize(stored)


@router.get("")
def list_research(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.scalars(
        select(DeepResearch)
        .where(DeepResearch.user_id == user.id)
        .order_by(DeepResearch.created_at.desc())
        .limit(20)
    ).all()
    return {"results": [_serialize(r) for r in rows]}


@router.get("/{research_id}")
def get_research(
    research_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.scalar(
        select(DeepResearch).where(
            DeepResearch.id == research_id, DeepResearch.user_id == user.id
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Research not found")
    return _serialize(row)
