# backend/app/api/plugins.py
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.plugins import PluginError, PluginManager

log = logging.getLogger(__name__)

router = APIRouter(tags=["plugins"])


class InstallRequest(BaseModel):
    manifest: Dict[str, Any]


class ToggleRequest(BaseModel):
    enabled: bool


class ExecuteRequest(BaseModel):
    plugin: str
    command: str
    args: Optional[Dict[str, Any]] = None


@router.get("/api/plugins")
def list_plugins(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"plugins": PluginManager(db).list(user.id)}


@router.post("/api/plugins/install")
def install_plugin(payload: InstallRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pm = PluginManager(db)
    try:
        plugin = pm.install(user.id, payload.manifest)
    except PluginError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    return pm._serialize(plugin)


@router.post("/api/plugins/{plugin_id}/toggle")
def toggle_plugin(plugin_id: str, payload: ToggleRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    toggled = PluginManager(db).toggle(user.id, plugin_id, payload.enabled)
    if toggled is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    db.commit()
    return toggled


@router.delete("/api/plugins/{plugin_id}")
def uninstall_plugin(plugin_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not PluginManager(db).uninstall(user.id, plugin_id):
        raise HTTPException(status_code=404, detail="Plugin not found")
    db.commit()
    return {"status": "ok"}


@router.get("/api/plugins/commands")
def plugin_commands(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"commands": PluginManager(db).commands(user.id)}


@router.post("/api/plugins/execute")
def execute_plugin(payload: ExecuteRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pm = PluginManager(db)
    try:
        result = pm.execute(user.id, payload.plugin, payload.command, payload.args)
    except PluginError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result


@router.get("/api/plugins/marketplace")
def plugin_marketplace(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"plugins": PluginManager(db).marketplace()}
