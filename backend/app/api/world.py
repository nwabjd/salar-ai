# backend/app/api/world.py
"""World Model API — inspect and feed the continuously-updated world graph."""
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.agent import execute_tool
from ..services.world_model import (
    EvolutionEngine,
    MemorySyncService,
    SituationActionPlanner,
    SituationEngine,
    WorldGraph,
    WorldIngestor,
    WorldSimulator,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/world", tags=["world"])


class ObserveBody(BaseModel):
    source: str = Field(..., min_length=1)
    event_type: str = Field(..., min_length=1)
    payload: dict = Field(default_factory=dict)


class UpsertBody(BaseModel):
    entity_type: str = Field(..., min_length=1)
    key: str = Field(..., min_length=1)
    name: str = ""
    summary: str = ""
    props: dict = Field(default_factory=dict)
    source: str = "api"


class RelateBody(BaseModel):
    from_type: str = Field(..., min_length=1)
    from_key: str = Field(..., min_length=1)
    relation: str = Field(..., min_length=1)
    to_type: str = Field(..., min_length=1)
    to_key: str = Field(..., min_length=1)
    source: str = "api"
    weight: float = 1.0


class SituationBody(BaseModel):
    kind: str = Field(..., min_length=1)
    severity: str = "low"
    title: str = Field(..., min_length=1)
    summary: str = ""


class SimulateBody(BaseModel):
    changes: List[Dict[str, Any]] = Field(default_factory=list)


class ExecuteActionBody(BaseModel):
    situation_kind: str = Field(..., min_length=1)
    action_title: str = Field(..., min_length=1)
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    risk: str = "low"
    confirmed: bool = False


class RecordExecutionBody(BaseModel):
    situation_kind: str = Field(..., min_length=1)
    action_title: str = Field(..., min_length=1)
    outcome: str = "unknown"
    resolved: bool = False
    detail: str = ""


class RecordResolutionBody(BaseModel):
    situation_kind: str = Field(..., min_length=1)
    resolved: bool = True


@router.get("/snapshot")
def world_snapshot(
    center_type: str = "",
    center_key: str = "",
    depth: int = 2,
    limit: int = 400,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    graph = WorldGraph(db)
    return graph.snapshot(
        user.id,
        center_type=center_type or None,
        center_key=center_key or None,
        depth=depth,
        limit=limit,
    )


@router.get("/entities")
def world_entities(
    entity_type: str = "",
    limit: int = 200,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    graph = WorldGraph(db)
    return [WorldGraph._node(e) for e in graph.entities(user.id, entity_type=entity_type or None, limit=limit)]


@router.get("/search")
def world_search(
    q: str = "",
    limit: int = 25,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not q.strip():
        return []
    graph = WorldGraph(db)
    return [WorldGraph._node(e) for e in graph.search(user.id, q, limit=limit)]


@router.get("/situations")
def world_situations(
    limit: int = 30,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    graph = WorldGraph(db)
    engine = SituationEngine(graph)
    return engine.situations(user.id, limit=limit)


@router.get("/actions")
def world_actions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    graph = WorldGraph(db)
    engine = SituationEngine(graph)
    sits = engine.situations(user.id)
    planner = SituationActionPlanner(db)
    return planner.propose_actions(user.id, sits)


@router.post("/observe")
def world_observe(
    body: ObserveBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    graph = WorldGraph(db)
    ingestor = WorldIngestor(graph)
    result = ingestor.ingest(user.id, source=body.source, event_type=body.event_type, payload=body.payload)
    db.commit()
    return result


@router.post("/entities")
def world_upsert_entity(
    body: UpsertBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    graph = WorldGraph(db)
    entity = graph.upsert_entity(
        user.id, body.entity_type, body.key,
        name=body.name, summary=body.summary, props=body.props, source=body.source,
    )
    db.commit()
    return WorldGraph._node(entity)


@router.post("/relations")
def world_relate(
    body: RelateBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    graph = WorldGraph(db)
    rel = graph.relate(
        user.id, body.from_type, body.from_key, body.relation,
        body.to_type, body.to_key, source=body.source, weight=body.weight,
    )
    db.commit()
    if rel is None:
        raise HTTPException(status_code=404, detail="Could not create relation")
    return {"id": rel.id, "relation": rel.relation}


@router.post("/sync")
def world_sync(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually trigger memory unification + connected-source ingestion."""
    syncer = MemorySyncService(db)
    counts = syncer.sync_all(user.id)
    syncer.sync_relations(user.id)
    db.commit()
    return {"ok": True, **counts}


@router.post("/situations")
def world_report_situation(
    body: SituationBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    graph = WorldGraph(db)
    ingestor = WorldIngestor(graph)
    entity = ingestor.ingest_generic(user.id, {
        "title": body.title,
        "summary": body.summary,
        "type": body.kind,
        "source": "situation_report",
    })
    graph.journal(user.id, source="situation_report", event_type="situation", entity_id=entity, payload=body.model_dump())
    db.commit()
    return {"ok": True, "entity_id": entity}


@router.post("/simulate")
def world_simulate(
    body: SimulateBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    graph = WorldGraph(db)
    engine = SituationEngine(graph)
    simulator = WorldSimulator(graph, engine)
    result = simulator.simulate(user.id, body.changes)
    return result.to_dict()


@router.get("/policies")
def world_policies(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return EvolutionEngine(db).policies(user.id)


@router.post("/executions")
def world_record_execution(
    body: RecordExecutionBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ex_id = EvolutionEngine(db).record_execution(
        user.id, body.situation_kind, body.action_title,
        outcome=body.outcome, resolved=body.resolved, detail=body.detail,
    )
    db.commit()
    return {"ok": True, "execution_id": ex_id}


@router.post("/resolutions")
def world_record_resolution(
    body: RecordResolutionBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    EvolutionEngine(db).record_resolution(user.id, body.situation_kind, resolved=body.resolved)
    db.commit()
    return {"ok": True}


@router.post("/evolve")
def world_evolve(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    engine = EvolutionEngine(db)
    updated = engine.evolve(user.id)
    db.commit()
    return {"ok": True, "policies": updated}


@router.post("/actions/execute")
def world_execute_action(
    body: ExecuteActionBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.risk == "high" and not body.confirmed:
        raise HTTPException(status_code=428, detail="High-risk actions require confirmed=true")

    results = []
    all_success = True
    for tc in body.tool_calls:
        name = tc.get("name", "")
        args = tc.get("args", {})
        try:
            import asyncio
            outcome = asyncio.run(execute_tool(name, args, user.id, db, is_admin=user.is_admin))
            results.append({"tool": name, "result": outcome})
            if outcome.get("error"):
                all_success = False
        except Exception as exc:
            results.append({"tool": name, "result": {"error": str(exc)}})
            all_success = False

    engine = EvolutionEngine(db)
    engine.record_execution(
        user.id, body.situation_kind, body.action_title,
        body.tool_calls,
        outcome="success" if all_success else "failure",
    )
    db.commit()

    return {"ok": True, "results": results, "outcome": "success" if all_success else "failure"}
