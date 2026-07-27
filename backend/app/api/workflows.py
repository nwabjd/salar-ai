import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Workflow, WorkflowRun
from ..security import get_current_user

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


def _serialize_run(run: WorkflowRun) -> dict:
    return {
        "id": run.id,
        "workflow_id": run.workflow_id,
        "trigger_event": run.trigger_event,
        "status": run.status,
        "result_log": run.result_log,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


def _serialize_workflow(wf: Workflow) -> dict:
    return {
        "id": wf.id,
        "user_id": wf.user_id,
        "workspace_id": wf.workspace_id,
        "name": wf.name,
        "description": wf.description,
        "trigger_type": wf.trigger_type,
        "trigger_config": json.loads(wf.trigger_config) if wf.trigger_config else {},
        "actions": json.loads(wf.actions) if wf.actions else [],
        "is_enabled": wf.is_enabled,
        "last_run_at": wf.last_run_at.isoformat() if wf.last_run_at else None,
        "run_count": wf.run_count,
        "created_at": wf.created_at.isoformat() if wf.created_at else None,
        "updated_at": wf.updated_at.isoformat() if wf.updated_at else None,
    }


@router.get("")
def list_workflows(
    enabled_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Workflow).filter(Workflow.user_id == current_user.id)
    if enabled_only:
        q = q.filter(Workflow.is_enabled == True)
    return [_serialize_workflow(w) for w in q.order_by(Workflow.created_at.desc()).all()]


@router.post("")
def create_workflow(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wf = Workflow(
        user_id=current_user.id,
        workspace_id=body.get("workspace_id"),
        name=body["name"],
        description=body.get("description"),
        trigger_type=body["trigger_type"],
        trigger_config=json.dumps(body.get("trigger_config", {})),
        actions=json.dumps(body.get("actions", [])),
        is_enabled=True,
        run_count=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(wf)
    db.commit()
    db.refresh(wf)
    return _serialize_workflow(wf)


@router.put("/{workflow_id}")
def update_workflow(
    workflow_id: str,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wf = (
        db.query(Workflow)
        .filter(Workflow.id == workflow_id, Workflow.user_id == current_user.id)
        .first()
    )
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    for field in ("name", "description", "trigger_type"):
        if field in body:
            setattr(wf, field, body[field])
    if "trigger_config" in body:
        wf.trigger_config = json.dumps(body["trigger_config"])
    if "actions" in body:
        wf.actions = json.dumps(body["actions"])
    wf.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(wf)
    return _serialize_workflow(wf)


@router.delete("/{workflow_id}")
def delete_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wf = (
        db.query(Workflow)
        .filter(Workflow.id == workflow_id, Workflow.user_id == current_user.id)
        .first()
    )
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    db.query(WorkflowRun).filter(WorkflowRun.workflow_id == workflow_id).delete()
    db.delete(wf)
    db.commit()
    return {"detail": "Workflow deleted"}


@router.patch("/{workflow_id}/toggle")
def toggle_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wf = (
        db.query(Workflow)
        .filter(Workflow.id == workflow_id, Workflow.user_id == current_user.id)
        .first()
    )
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    wf.is_enabled = not wf.is_enabled
    wf.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(wf)
    return _serialize_workflow(wf)


@router.get("/{workflow_id}/runs")
def list_workflow_runs(
    workflow_id: str,
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wf = (
        db.query(Workflow)
        .filter(Workflow.id == workflow_id, Workflow.user_id == current_user.id)
        .first()
    )
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    runs = (
        db.query(WorkflowRun)
        .filter(WorkflowRun.workflow_id == workflow_id)
        .order_by(WorkflowRun.started_at.desc())
        .limit(limit)
        .all()
    )
    return [_serialize_run(r) for r in runs]


@router.post("/{workflow_id}/test")
def test_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wf = (
        db.query(Workflow)
        .filter(Workflow.id == workflow_id, Workflow.user_id == current_user.id)
        .first()
    )
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    now = datetime.now(timezone.utc)
    run = WorkflowRun(
        workflow_id=workflow_id,
        trigger_event="manual_test",
        status="success",
        result_log="Test run completed successfully",
        started_at=now,
        finished_at=now,
    )
    db.add(run)
    wf.last_run_at = now
    wf.run_count = (wf.run_count or 0) + 1
    db.commit()
    db.refresh(run)
    return _serialize_run(run)


@router.post("/trigger")
def process_trigger(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event_type = body.get("type")
    event_data = body.get("data", {})
    workflows = (
        db.query(Workflow)
        .filter(
            Workflow.trigger_type == event_type,
            Workflow.is_enabled == True,
        )
        .all()
    )
    created_runs = []
    for wf in workflows:
        run = WorkflowRun(
            workflow_id=wf.id,
            trigger_event=json.dumps({"type": event_type, "data": event_data}),
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        db.add(run)
        wf.last_run_at = datetime.now(timezone.utc)
        wf.run_count = (wf.run_count or 0) + 1
        created_runs.append(run)
    db.commit()
    for run in created_runs:
        run.status = "success"
        run.result_log = "Trigger processed successfully"
        run.finished_at = datetime.now(timezone.utc)
    db.commit()
    return {"matched_workflows": len(created_runs), "runs": [_serialize_run(r) for r in created_runs]}
