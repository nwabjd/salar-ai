# backend/app/api/swarm.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
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
def create_swarm_run(
    body: DecomposeBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    swarm = AgentSwarm(db)
    agents = swarm.decompose(body.goal)
    run = swarm.create_run(current_user.id, body.goal, agents)
    db.commit()
    return {"run": swarm.agent_summary(run)}
