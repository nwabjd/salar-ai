# backend/app/api/missions.py
import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Mission, MissionEvent, MissionStep, User
from ..security import get_current_user
from ..services.missions.runner import MissionConflict, MissionRunner

router = APIRouter(prefix="/api/missions", tags=["missions"])


def _get_runner(request: Request) -> MissionRunner:
    runner = getattr(request.app.state, "mission_runner", None)
    if runner is None:
        raise HTTPException(status_code=503, detail="Mission runner not available")
    return runner


def _run(coro):
    # FastAPI runs plain `def` endpoints in a threadpool worker thread. On
    # Python 3.9 there is no event loop in that thread, so get_event_loop()
    # raises RuntimeError; create one for the thread instead.
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def _serialize_mission(m: Mission, steps=None, events=None) -> dict:
    data = {
        "id": m.id,
        "goal": m.goal,
        "mode": m.mode,
        "status": m.status,
        "step_count": m.step_count,
        "completed_count": m.completed_count,
        "total_attempts": m.total_attempts,
        "replan_count": m.replan_count,
        "result_summary": m.result_summary,
        "error": m.error,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "started_at": m.started_at.isoformat() if m.started_at else None,
        "finished_at": m.finished_at.isoformat() if m.finished_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }
    if steps is not None:
        data["steps"] = [_serialize_step(s) for s in steps]
    if events is not None:
        data["events"] = [_serialize_event(e) for e in events]
    return data


def _serialize_step(s: MissionStep) -> dict:
    return {
        "id": s.id,
        "sequence": s.sequence,
        "tool": s.tool,
        "args_json": s.args_json,
        "danger_level": s.danger_level,
        "status": s.status,
        "output_json": s.output_json,
        "error": s.error,
        "approval_note": s.approval_note,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "finished_at": s.finished_at.isoformat() if s.finished_at else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _serialize_event(e) -> dict:
    return {
        "id": e.id,
        "sequence": e.sequence,
        "kind": e.kind,
        "detail_json": e.detail_json,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


def _find_owned_mission(db: Session, mission_id: str, user_id: str) -> Mission:
    m = db.scalar(select(Mission).where(Mission.id == mission_id, Mission.user_id == user_id))
    if not m:
        raise HTTPException(status_code=404, detail="Mission not found")
    return m


class LaunchBody(BaseModel):
    goal: str
    mode: str = "autonomous"


@router.post("")
def launch_mission(
    body: LaunchBody,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    runner = _get_runner(request)
    try:
        result = _run(runner.launch(current_user.id, body.goal, mode=body.mode))
    except MissionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return result


@router.get("")
def list_missions(
    limit: int = 20,
    status: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(Mission).where(Mission.user_id == current_user.id)
    if status:
        q = q.where(Mission.status == status)
    missions = db.scalars(q.order_by(Mission.created_at.desc()).limit(limit)).all()
    return [_serialize_mission(m) for m in missions]


@router.get("/{mission_id}")
def get_mission(
    mission_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    m = _find_owned_mission(db, mission_id, current_user.id)
    steps = db.scalars(
        select(MissionStep).where(MissionStep.mission_id == mission_id).order_by(MissionStep.sequence.asc())
    ).all()
    events = db.scalars(
        select(MissionEvent).where(MissionEvent.mission_id == mission_id).order_by(MissionEvent.sequence.asc()).limit(50)
    ).all()
    return _serialize_mission(m, steps=steps, events=events)


@router.get("/{mission_id}/events")
def list_events(
    mission_id: str,
    since_sequence: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    m = _find_owned_mission(db, mission_id, current_user.id)
    from ..services.missions.events import MissionEventStore
    events = MissionEventStore(db).recent(mission_id, limit=200, since_sequence=since_sequence or None)
    return [_serialize_event(e) for e in events]


@router.post("/{mission_id}/cancel")
def cancel_mission(
    mission_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    runner = _get_runner(request)
    m = _find_owned_mission(db, mission_id, current_user.id)
    _run(runner.cancel(mission_id))
    return {"status": "cancelled", "id": mission_id}


@router.post("/{mission_id}/steps/{step_id}/approve")
def approve_step(
    mission_id: str,
    step_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    runner = _get_runner(request)
    m = _find_owned_mission(db, mission_id, current_user.id)
    step = db.get(MissionStep, step_id)
    if not step or step.mission_id != mission_id:
        raise HTTPException(status_code=404, detail="Step not found")
    _run(runner.approve(mission_id, step_id))
    return {"status": "approved", "step_id": step_id}


@router.post("/{mission_id}/steps/{step_id}/deny")
def deny_step(
    mission_id: str,
    step_id: str,
    request: Request,
    body: dict = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    runner = _get_runner(request)
    m = _find_owned_mission(db, mission_id, current_user.id)
    step = db.get(MissionStep, step_id)
    if not step or step.mission_id != mission_id:
        raise HTTPException(status_code=404, detail="Step not found")
    note = (body or {}).get("note", "")
    _run(runner.deny(mission_id, step_id, note=note))
    return {"status": "denied", "step_id": step_id}
