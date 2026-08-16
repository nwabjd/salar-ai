# backend/app/api/core.py
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CoreTask, CoreTrace, CoreTraceStep, User
from ..security import get_current_user
from ..services.core.pipeline import CorePipeline

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/core", tags=["core"])


class RunBody(BaseModel):
    request: str = Field(..., min_length=1)
    goal: str = ""


class ApproveBody(BaseModel):
    approve: bool


def _get_pipeline(request: Request) -> CorePipeline:
    pipeline = getattr(request.app.state, "core_pipeline", None)
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Core pipeline not available")
    return pipeline


def _serialize_trace(t: CoreTrace, steps=None) -> dict:
    data = {
        "id": t.id,
        "task_id": t.task_id,
        "status": t.status,
        "steps_count": t.steps_count,
        "started_at": t.started_at.isoformat() if t.started_at else None,
        "finished_at": t.finished_at.isoformat() if t.finished_at else None,
    }
    if steps is not None:
        data["steps"] = [
            {
                "id": s.id,
                "stage": s.stage,
                "detail": s.detail_json,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "finished_at": s.finished_at.isoformat() if s.finished_at else None,
                "duration_ms": s.duration_ms,
            }
            for s in steps
        ]
    return data


def _find_owned_task(db: Session, task_id: str, user_id: str) -> CoreTask:
    task = db.get(CoreTask, task_id)
    if task is None or task.user_id != user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/run")
async def run_task(
    body: RunBody,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pipeline = _get_pipeline(request)
    result = await pipeline.run(body.request, current_user.id, db_session=db)
    return result.to_dict()


@router.post("/run/{task_id}/approve")
async def approve_task(
    task_id: str,
    body: ApproveBody,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pipeline = _get_pipeline(request)
    task = _find_owned_task(db, task_id, current_user.id)
    try:
        result = await pipeline.approve(task.id, body.approve, db_session=db)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return result.to_dict()


@router.get("/traces/{trace_id}")
def get_trace(
    trace_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trace = db.get(CoreTrace, trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    task = db.get(CoreTask, trace.task_id)
    if task is None or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Trace not found")
    steps = db.scalars(
        select(CoreTraceStep).where(CoreTraceStep.trace_id == trace_id).order_by(CoreTraceStep.started_at.asc())
    ).all()
    return _serialize_trace(trace, steps=steps)


@router.get("/traces")
def list_traces(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task_ids = select(CoreTask.id).where(CoreTask.user_id == current_user.id)
    traces = db.scalars(
        select(CoreTrace)
        .where(CoreTrace.task_id.in_(task_ids))
        .order_by(CoreTrace.started_at.desc())
        .limit(limit)
    ).all()
    return [_serialize_trace(t) for t in traces]


@router.get("/status")
def status(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    runtime = getattr(request.app.state, "core_runtime", None)
    supervisor = getattr(request.app.state, "supervisor", None)
    bus = getattr(request.app.state, "core_bus", None)
    live = runtime.live_agents(db_session=db) if runtime is not None else []
    alerts = [a.to_dict() for a in supervisor.alerts] if supervisor is not None else []
    bus_events_count = bus.published_count if bus is not None else 0
    return {"live_agents": live, "alerts": alerts, "bus_events_count": bus_events_count}
