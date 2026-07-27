"""Alerts endpoints — manage alert rules and view triggered alerts."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from ..security import get_current_user
from ..models import User

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

_alert_engine = None


def get_engine():
    global _alert_engine
    if _alert_engine is None:
        from ..services.alerts import AlertEngine
        _alert_engine = AlertEngine()
    return _alert_engine


class RuleCreateRequest(BaseModel):
    name: str
    type: str
    config: dict = {}
    severity: str = "warning"


class RuleToggleRequest(BaseModel):
    enabled: bool


@router.get("/rules")
def list_rules(user: User = Depends(get_current_user)):
    engine = get_engine()
    return {"rules": engine.list_rules()}


@router.post("/rules")
def create_rule(req: RuleCreateRequest, user: User = Depends(get_current_user)):
    engine = get_engine()
    return engine.add_rule(req.name, req.type, req.config, req.severity)


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: str, user: User = Depends(get_current_user)):
    engine = get_engine()
    return engine.remove_rule(rule_id)


@router.put("/rules/{rule_id}/toggle")
def toggle_rule(rule_id: str, req: RuleToggleRequest, user: User = Depends(get_current_user)):
    engine = get_engine()
    return engine.toggle_rule(rule_id, req.enabled)


@router.get("/triggered")
def list_triggered(limit: int = 50, unacked_only: bool = False, user: User = Depends(get_current_user)):
    engine = get_engine()
    return {"alerts": engine.list_triggered(limit, unacked_only)}


@router.post("/triggered/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str, user: User = Depends(get_current_user)):
    engine = get_engine()
    return engine.acknowledge(alert_id)
