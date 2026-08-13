# backend/app/services/automation.py
import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from ..models import Notification, token_id, utcnow

log = logging.getLogger(__name__)


class AutomationManager:
    """Bridges intel events, workflows, and missions into user notifications + actions."""

    def __init__(self, db) -> None:
        self.db = db

    def process_intel_event(self, user_id: str, event) -> Optional[Notification]:
        """Convert a notable intel event into a notification (auto-routed by kind)."""
        if not event:
            return None
        from .notifications import NotificationCenter
        nc = NotificationCenter(self.db)
        if event.kind in ("email_bill", "email_important", "email_action"):
            return nc.push(user_id, "email", event.title, body=event.summary, severity=event.severity or "info")
        if event.kind in ("guardian", "high_cpu", "low_storage", "failed_build"):
            return nc.push(user_id, "alert", event.title, body=event.summary, severity=event.severity or "warning")
        if event.kind == "mission_event":
            return nc.push(user_id, "mission", event.title, body=event.summary, severity="info")
        if event.kind == "eod":
            return nc.push(user_id, "system", event.title, body="Your end-of-day summary is ready.", severity="info")
        return None
