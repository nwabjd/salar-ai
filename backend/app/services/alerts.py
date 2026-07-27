"""Proactive alert engine — watches system conditions and triggers notifications."""

import asyncio
import json
import time
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Callable
from enum import Enum

log = logging.getLogger(__name__)


class AlertType(str, Enum):
    DISK_USAGE = "disk_usage"
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    EMAIL_FROM = "email_from"
    EMAIL_UNREAD = "email_unread"
    CALENDAR_UPCOMING = "calendar_upcoming"
    SERVICE_DOWN = "service_down"
    CUSTOM = "custom"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertRule:
    def __init__(self, id: str, name: str, alert_type: AlertType, config: dict,
                 severity: AlertSeverity = AlertSeverity.WARNING, enabled: bool = True):
        self.id = id
        self.name = name
        self.type = alert_type
        self.config = config
        self.severity = severity
        self.enabled = enabled
        self.last_triggered: Optional[float] = None
        self.cooldown_seconds: int = config.get("cooldown", 3600)  # 1 hour default

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "config": self.config,
            "severity": self.severity.value,
            "enabled": self.enabled,
            "last_triggered": self.last_triggered,
        }

    def should_trigger(self) -> bool:
        if not self.enabled:
            return False
        if self.last_triggered and (time.time() - self.last_triggered) < self.cooldown_seconds:
            return False
        return True


class TriggeredAlert:
    def __init__(self, rule_id: str, rule_name: str, severity: str, message: str, details: dict = None):
        self.id = f"alert-{int(time.time()*1000)}"
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.severity = severity
        self.message = message
        self.details = details or {}
        self.timestamp = time.time()
        self.acknowledged = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "severity": self.severity,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp,
            "time_str": datetime.fromtimestamp(self.timestamp).strftime("%Y-%m-%d %H:%M:%S"),
            "acknowledged": self.acknowledged,
        }


class AlertEngine:
    def __init__(self):
        self.rules: Dict[str, AlertRule] = {}
        self.triggered: List[TriggeredAlert] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._callbacks: List[Callable] = []

    def on_alert(self, callback: Callable):
        self._callbacks.append(callback)

    def add_rule(self, name: str, alert_type: str, config: dict, severity: str = "warning") -> dict:
        import uuid
        rule_id = str(uuid.uuid4())[:8]
        rule = AlertRule(
            id=rule_id, name=name,
            alert_type=AlertType(alert_type),
            config=config,
            severity=AlertSeverity(severity),
        )
        self.rules[rule_id] = rule
        return rule.to_dict()

    def remove_rule(self, rule_id: str) -> dict:
        if rule_id in self.rules:
            del self.rules[rule_id]
            return {"status": "removed", "id": rule_id}
        return {"error": f"Rule {rule_id} not found"}

    def toggle_rule(self, rule_id: str, enabled: bool) -> dict:
        if rule_id in self.rules:
            self.rules[rule_id].enabled = enabled
            return {"status": "updated", "id": rule_id, "enabled": enabled}
        return {"error": f"Rule {rule_id} not found"}

    def list_rules(self) -> List[dict]:
        return [r.to_dict() for r in self.rules.values()]

    def list_triggered(self, limit: int = 50, unacked_only: bool = False) -> List[dict]:
        alerts = self.triggered
        if unacked_only:
            alerts = [a for a in alerts if not a.acknowledged]
        return [a.to_dict() for a in alerts[-limit:]]

    def acknowledge(self, alert_id: str) -> dict:
        for a in self.triggered:
            if a.id == alert_id:
                a.acknowledged = True
                return {"status": "acknowledged", "id": alert_id}
        return {"error": f"Alert {alert_id} not found"}

    def _fire(self, rule: AlertRule, message: str, details: dict = None):
        alert = TriggeredAlert(rule.id, rule.name, rule.severity.value, message, details)
        self.triggered.append(alert)
        if len(self.triggered) > 500:
            self.triggered = self.triggered[-300:]
        rule.last_triggered = time.time()
        log.info("ALERT [%s] %s: %s", rule.severity.value, rule.name, message)
        for cb in self._callbacks:
            try:
                cb(alert)
            except Exception:
                pass

    async def _check_rules(self):
        import psutil
        for rule in list(self.rules.values()):
            if not rule.should_trigger():
                continue
            try:
                if rule.type == AlertType.DISK_USAGE:
                    threshold = rule.config.get("threshold", 90)
                    mountpoint = rule.config.get("mountpoint", "C:\\")
                    usage = psutil.disk_usage(mountpoint)
                    if usage.percent >= threshold:
                        self._fire(rule, f"Disk {mountpoint} is {usage.percent}% full (threshold: {threshold}%)",
                                   {"mountpoint": mountpoint, "percent": usage.percent, "free_gb": round(usage.free / (1024**3), 2)})

                elif rule.type == AlertType.CPU_USAGE:
                    threshold = rule.config.get("threshold", 95)
                    duration = rule.config.get("duration", 60)
                    cpu = psutil.cpu_percent(interval=1)
                    if cpu >= threshold:
                        self._fire(rule, f"CPU usage is {cpu}% (threshold: {threshold}%)",
                                   {"cpu_percent": cpu, "threshold": threshold})

                elif rule.type == AlertType.MEMORY_USAGE:
                    threshold = rule.config.get("threshold", 90)
                    mem = psutil.virtual_memory()
                    if mem.percent >= threshold:
                        self._fire(rule, f"Memory usage is {mem.percent}% (threshold: {threshold}%)",
                                   {"percent": mem.percent, "used_gb": round(mem.used / (1024**3), 2)})

                elif rule.type == AlertType.EMAIL_FROM:
                    from .state import email_accounts
                    sender = rule.config.get("sender", "")
                    folder = rule.config.get("folder", "INBOX")
                    if sender and email_accounts:
                        for uid, cfg in email_accounts.items():
                            try:
                                from .email_client import EmailAccount
                                client = EmailAccount(**cfg)
                                recent = client.search_emails(folder=folder, query=f'FROM "{sender}"', limit=5)
                                if recent:
                                    self._fire(rule, f"Email from {sender}: {recent[0].get('subject', '(no subject)')}",
                                               {"sender": sender, "folder": folder, "count": len(recent), "latest": recent[0]})
                            except Exception as e:
                                log.warning("EMAIL_FROM check failed for %s: %s", uid, e)

                elif rule.type == AlertType.EMAIL_UNREAD:
                    from .state import email_accounts
                    threshold = rule.config.get("threshold", 10)
                    folder = rule.config.get("folder", "INBOX")
                    if email_accounts:
                        for uid, cfg in email_accounts.items():
                            try:
                                from .email_client import EmailAccount
                                client = EmailAccount(**cfg)
                                count = client.get_unread_count(folder)
                                if count >= threshold:
                                    self._fire(rule, f"Unread emails: {count} (threshold: {threshold})",
                                               {"folder": folder, "count": count, "threshold": threshold})
                            except Exception as e:
                                log.warning("EMAIL_UNREAD check failed for %s: %s", uid, e)

                elif rule.type == AlertType.SERVICE_DOWN:
                    url = rule.config.get("url", "")
                    if url:
                        import httpx
                        try:
                            resp = httpx.get(url, timeout=5)
                            if resp.status_code >= 500:
                                self._fire(rule, f"Service at {url} returned {resp.status_code}",
                                           {"url": url, "status": resp.status_code})
                        except Exception as e:
                            self._fire(rule, f"Service at {url} is unreachable: {e}",
                                       {"url": url, "error": str(e)})

            except Exception as e:
                log.error("Alert check failed for rule %s: %s", rule.id, e)

    async def start(self, interval: int = 60):
        if self._running:
            return
        self._running = True
        log.info("Alert engine started (interval: %ds)", interval)

        async def loop():
            while self._running:
                await self._check_rules()
                await asyncio.sleep(interval)

        self._task = asyncio.create_task(loop())

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
