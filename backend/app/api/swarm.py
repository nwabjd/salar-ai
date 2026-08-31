# backend/app/api/swarm.py
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..database import get_db
from ..models import AgentRun, User
from ..security import get_current_user
from ..services.swarm import AGENT_SPECS, AgentSwarm

router = APIRouter(prefix="/api/swarm", tags=["swarm"])


@router.get("/agents")
def list_agents():
    return {
        "agents": [
            {"name": name, "description": spec["description"], "tools": spec["tools"]}
            for name, spec in AGENT_SPECS.items()
        ]
    }


class DecomposeBody(BaseModel):
    goal: str


@router.post("/decompose")
def decompose(
    body: DecomposeBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    swarm = AgentSwarm(db)
    return {"agents": swarm.decompose(body.goal)}


@router.post("/run")
async def create_and_execute_swarm_run(
    body: DecomposeBody,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    coordinator = getattr(request.app.state, "coordinator", None)
    swarm = AgentSwarm(db, coordinator=coordinator)
    agents = swarm.decompose(body.goal)
    run = swarm.create_run(current_user.id, body.goal, agents)
    db.commit()

    # Execute asynchronously across the swarm
    summary = await swarm.execute_swarm(run)
    return {"run": summary}


@router.get("/runs")
def list_swarm_runs(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    runs = list(
        db.scalars(
            select(AgentRun)
            .where(AgentRun.user_id == current_user.id, AgentRun.kind == "swarm")
            .order_by(AgentRun.created_at.desc())
            .limit(min(max(limit, 1), 50))
        )
    )
    swarm = AgentSwarm(db)
    return {"runs": [swarm.agent_summary(r) for r in runs]}


@router.get("/runs/{run_id}")
def get_swarm_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = db.scalar(
        select(AgentRun).where(
            AgentRun.id == run_id,
            AgentRun.user_id == current_user.id,
        )
    )
    if not run:
        raise HTTPException(status_code=404, detail="Swarm run not found")
    swarm = AgentSwarm(db)
    return {"run": swarm.agent_summary(run)}
