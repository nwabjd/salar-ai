# backend/app/api/privacy_prefs.py
import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.local_ai import LocalAIMode

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/privacy", tags=["privacy"])


class PreferencesUpdate(BaseModel):
    local_ai_mode: Optional[bool] = None
    data_retention_days: Optional[int] = None
    action_log_enabled: Optional[bool] = None
    intel_enabled: Optional[bool] = None
    analytics_enabled: Optional[bool] = None


def _prefs_dict(p) -> dict:
    return {
        "local_ai_mode": p.local_ai_mode,
        "data_retention_days": p.data_retention_days,
        "action_log_enabled": p.action_log_enabled,
        "intel_enabled": p.intel_enabled,
        "analytics_enabled": p.analytics_enabled,
    }


@router.get("/preferences")
def get_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _prefs_dict(LocalAIMode(db).prefs_for(current_user.id))


@router.put("/preferences")
def update_preferences(
    body: PreferencesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lai = LocalAIMode(db)
    lai.update(current_user.id, **body.model_dump(exclude_none=True))
    db.commit()
    return _prefs_dict(lai.prefs_for(current_user.id))
