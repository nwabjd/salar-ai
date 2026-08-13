# backend/app/services/local_ai.py
import logging
from typing import Any, Dict

from sqlalchemy import select

from ..models import PrivacyPreferences

log = logging.getLogger(__name__)


class LocalAIMode:
    def __init__(self, db) -> None:
        self.db = db

    def prefs_for(self, user_id: str) -> PrivacyPreferences:
        row = self.db.scalar(select(PrivacyPreferences).where(PrivacyPreferences.user_id == user_id))
        if row is None:
            row = PrivacyPreferences(user_id=user_id)
            self.db.add(row)
            self.db.flush()
        return row

    def update(self, user_id: str, **kwargs) -> PrivacyPreferences:
        row = self.prefs_for(user_id)
        allowed = {"local_ai_mode", "data_retention_days", "action_log_enabled", "intel_enabled", "analytics_enabled"}
        for k, v in kwargs.items():
            if k in allowed:
                setattr(row, k, v)
        return row

    def evaluate(self, user_id: str, feature: str) -> Dict[str, Any]:
        """Whether a feature runs locally or in the cloud under current prefs."""
        prefs = self.prefs_for(user_id)
        cloud_requiring = {"vision", "deep_research", "decision_simulator"}
        local_capable = {"stt", "tts", "wake_word", "vad", "screen"}
        if feature in cloud_requiring:
            return {"feature": feature, "location": "cloud", "permitted": True, "local_ai_mode": prefs.local_ai_mode}
        if feature in local_capable:
            return {"feature": feature, "location": "local", "permitted": True, "local_ai_mode": prefs.local_ai_mode}
        return {"feature": feature, "location": "cloud", "permitted": True, "local_ai_mode": prefs.local_ai_mode}
