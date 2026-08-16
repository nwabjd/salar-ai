# backend/app/services/world_model/situations.py
"""SituationEngine — turns the world graph into 'what is happening right now'.

Rather than answering 'what facts exist', the engine answers questions like:

- Project X has a deadline tomorrow, the latest build is failing, a
  collaborator emailed about the same issue, the repo is open, and the
  workstation has enough resources to test a fix.

Situations are rule-based, deterministic, and grounded in the graph plus a
few source tables (tasks, reminders, devices). The engine emits structured
Situation objects with a severity so callers can surface the most important
state first.
"""

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from ...models import Reminder, Task, utcnow

log = logging.getLogger(__name__)


class Situation:
    def __init__(
        self,
        *,
        kind: str,
        severity: str,
        title: str,
        summary: str = "",
        entity_ids: Optional[List[str]] = None,
        props: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.kind = kind
        self.severity = severity
        self.title = title
        self.summary = summary
        self.entity_ids = entity_ids or []
        self.props = props or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "severity": self.severity,
            "title": self.title,
            "summary": self.summary,
            "entity_ids": self.entity_ids,
            "props": self.props,
        }


class SituationEngine:
    def __init__(self, graph) -> None:
        self.graph = graph
        self.db = graph.db

    # ---------------- public entry point ----------------

    def situations(self, user_id: str, *, limit: int = 30) -> List[Dict[str, Any]]:
        out: List[Situation] = []

        project_entities = self.graph.entities(user_id, entity_type="project", limit=50)
        for project in project_entities:
            out.extend(self._project_situations(user_id, project))

        out.extend(self._device_situations(user_id))
        out.extend(self._timeboxed_tasks(user_id))
        out.extend(self._collaborator_signals(user_id))

        out.sort(key=lambda s: _SEVERITY_RANK.get(s.severity, 10))
        return [s.to_dict() for s in out[:limit]]

    def context_text(self, user_id: str, *, limit: int = 8) -> str:
        """Compact human-readable summary for injecting into LLM prompts.

        Returns an empty string when nothing is happening, so callers can
        simply omit the block instead of instructing the model about
        non-events.
        """
        situations = self.situations(user_id, limit=limit)
        if not situations:
            return ""
        lines = []
        for s in situations:
            line = f"- [{s['severity']}] {s['title']}"
            if s.get("summary"):
                line += f" — {s['summary'][:160]}"
            lines.append(line)
        return "\n".join(lines)

    def projected_outcomes(self, user_id: str, *, limit: int = 4) -> str:
        """Deterministic 'what happens if nothing changes' projection.

        A lightweight forward pass over current situations: deadline pressure
        counts down, failing builds stay broken, resource pressure escalates.
        Returns an empty string when there is nothing to project, so callers
        can omit the block instead of inventing outcomes.
        """
        situations = self.situations(user_id, limit=30)
        lines = []
        for s in situations:
            kind = s.get("kind")
            props = s.get("props", {})
            severity = s.get("severity", "low")

            if kind == "deadline_pressure":
                days_left = props.get("days_left")
                if days_left is not None:
                    try:
                        days = float(days_left)
                    except (TypeError, ValueError):
                        days = 0.0
                    if days <= 0:
                        lines.append(f"- {s['title']}: deadline has already passed — outcome is missed unless acted on today.")
                    elif days < 1:
                        lines.append(f"- {s['title']}: {days:.1f} days left — outcome is a missed deadline if untouched.")
                    else:
                        lines.append(f"- {s['title']}: {days:.1f} days left — closes in on the deadline if untouched.")
            elif kind == "failing_build":
                lines.append(f"- {s['title']}: stays broken until a fix lands — blocks the project's forward motion.")
            elif kind == "resource_pressure":
                lines.append(f"- {s['title']}: escalates — system may become unresponsive without freeing resources.")
            elif kind == "collaborator_activity":
                lines.append(f"- {s['title']}: unacknowledged outreach risks a stalled collaborator — respond to keep momentum.")

            if len(lines) >= limit:
                break
        return "\n".join(lines)

    # ---------------- per-project ----------------

    def _project_situations(self, user_id: str, project) -> List[Situation]:
        out: List[Situation] = []
        neighbors = self.graph.neighbors(user_id, project.id, limit=200)
        props = project.props

        files = [n for n in neighbors if n["entity"]["type"] == "file"]
        people = [n for n in neighbors if n["entity"]["type"] == "person"]
        apps = [n for n in neighbors if n["entity"]["type"] == "app"]
        open_count = 0
        for n in neighbors:
            if n["relation"] in ("has_open", "open_in") or n["entity"]["props"].get("open"):
                open_count += 1
        for app in apps:
            if app["entity"]["props"].get("open"):
                open_count += 1
                for edge in self.graph.neighbors(user_id, app["entity"]["id"], direction="out", limit=50):
                    if edge["relation"] == "has_open" and edge["entity"]["type"] == "file":
                        open_count += 1

        # Deadline pressure — deadlines are events with a `due` prop, or reminder-linked entities.
        deadline = props.get("deadline") or props.get("due")
        deadline_at = self._parse_dt(deadline)
        if deadline_at is not None:
            days_left = (deadline_at - utcnow()).total_seconds() / 86400
            if days_left <= 3:
                urgency = "critical" if days_left < 1 else "high" if days_left < 2 else "medium"
                out.append(Situation(
                    kind="deadline_pressure",
                    severity=urgency,
                    title=f"{project.name} has a deadline",
                    summary=self._human_remaining(days_left),
                    entity_ids=[project.id],
                    props={"due": deadline, "days_left": round(days_left, 1)},
                ))

        for e in neighbors:
            if e["entity"]["type"] in ("build", "job", "run") and e["entity"]["props"].get("status") == "failed":
                out.append(Situation(
                    kind="failing_build",
                    severity="high",
                    title=f"{project.name}: latest build is failing",
                    summary=e["entity"]["name"] or e["entity"]["key"],
                    entity_ids=[project.id, e["entity"]["id"]],
                    props=e["entity"]["props"],
                ))
                break

        # Collaborator signals: recent messages/emails from people touching the project.
        for person in people:
            signal = self._person_recent_signal(user_id, person["entity"]["id"])
            if signal:
                out.append(Situation(
                    kind="collaborator_activity",
                    severity="medium",
                    title=f"{person['entity']['name'] or person['entity']['key']} reached out about {project.name}",
                    summary=signal["summary"],
                    entity_ids=[project.id, person["entity"]["id"]],
                    props={"since_minutes": signal["minutes"], "channel": signal["channel"]},
                ))

        # Active context
        if open_count:
            out.append(Situation(
                kind="active_context",
                severity="low",
                title=f"{project.name} context is open",
                summary=f"{open_count} related files/apps open right now",
                entity_ids=[project.id],
                props={"open_count": open_count, "files": [f["entity"]["key"] for f in files[:5]]},
            ))
        return out

    # ---------------- device/resources ----------------

    def _device_situations(self, user_id: str) -> List[Situation]:
        out: List[Situation] = []
        devices = self.graph.entities(user_id, entity_type="device", limit=20)
        for device in devices:
            props = device.props
            cpu = self._to_float(props.get("cpu"))
            mem = self._to_float(props.get("memory"))
            if cpu is None and mem is None:
                continue
            if (cpu is not None and cpu > 90) or (mem is not None and mem > 90):
                out.append(Situation(
                    kind="resource_pressure",
                    severity="medium",
                    title=f"{device.name or device.key} is under heavy load",
                    summary=self._resource_summary(cpu, mem),
                    entity_ids=[device.id],
                    props={"cpu": cpu, "memory": mem},
                ))
        return out

    # ---------------- tasks ----------------

    def _timeboxed_tasks(self, user_id: str) -> List[Situation]:
        out: List[Situation] = []
        now = utcnow()
        due_soon = now + timedelta(hours=24)
        rows = self.db.scalars(
            select(Task).where(
                Task.user_id == user_id,
                Task.status.in_(["todo", "in_progress"]),
                Task.due_date.isnot(None),
                Task.due_date <= due_soon,
            )
        ).all()
        for task in rows:
            out.append(Situation(
                kind="task_due",
                severity="medium",
                title=f"Task due: {task.title}",
                summary=f"Due {task.due_date.strftime('%a %H:%M') if task.due_date else 'soon'}",
                props={"task_id": task.id, "due": task.due_date.isoformat() if task.due_date else None},
            ))
        return out

    # ---------------- reminders ----------------

    def _reminder_situations(self, user_id: str) -> List[Situation]:
        rows = self.db.scalars(
            select(Reminder).where(
                Reminder.user_id == user_id,
                Reminder.is_done.is_(False),
                Reminder.remind_at.isnot(None),
                Reminder.remind_at <= utcnow() + timedelta(hours=2),
            )
        ).all()
        out: List[Situation] = []
        for r in rows:
            out.append(Situation(
                kind="reminder_coming",
                severity="low",
                title=f"Reminder: {r.title}",
                summary=f"Scheduled {r.remind_at.strftime('%a %H:%M')}",
                props={"reminder_id": r.id, "remind_at": r.remind_at.isoformat()},
            ))
        return out

    # ---------------- collaborator signal extraction ----------------

    def _person_recent_signal(self, user_id: str, person_id: str) -> Optional[Dict[str, Any]]:
        """Find the most recent message/email entity from this person (within 48h)."""
        neighbors = self.graph.neighbors(user_id, person_id, direction="in", limit=50)
        now = utcnow()
        best = None
        for n in neighbors:
            if n["entity"]["type"] not in ("email", "message", "chat"):
                continue
            last_seen = self._parse_dt(n["entity"]["last_seen"])
            if last_seen is None:
                continue
            minutes = (now - last_seen).total_seconds() / 60
            if minutes > 48 * 60 or minutes < 0:
                continue
            if best is None or minutes < best["minutes"]:
                best = {
                    "minutes": round(minutes),
                    "channel": n["entity"]["type"],
                    "summary": (n["entity"]["summary"] or n["entity"]["name"] or "")[:200],
                }
        return best

    def _collaborator_signals(self, user_id: str) -> List[Situation]:
        """Orphan collaborator signals: recent inbound messages not tied to a project entity."""
        out: List[Situation] = []
        people = self.graph.entities(user_id, entity_type="person", limit=30)
        for person in people:
            signal = self._person_recent_signal(user_id, person.id)
            if signal and signal["minutes"] <= 30:
                project_links = self.graph.neighbors(user_id, person.id, relation="works_on", limit=5)
                if not project_links:
                    out.append(Situation(
                        kind="direct_message",
                        severity="low",
                        title=f"New message from {person.name or person.key}",
                        summary=signal["summary"],
                        entity_ids=[person.id],
                        props={"channel": signal["channel"], "minutes": signal["minutes"]},
                    ))
        return out

    # ---------------- helpers ----------------

    @staticmethod
    def _props(entity) -> Dict[str, Any]:
        try:
            return json.loads(entity.props_json or "{}")
        except Exception:
            return {}

    @staticmethod
    def _parse_dt(value: Any) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        text = str(value).strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            pass
        for fmt in ("%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(text, fmt)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed
            except ValueError:
                continue
        return None

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _human_remaining(days_left: float) -> str:
        if days_left < 1:
            hours = max(int(days_left * 24), 1)
            return f"Due in {hours}h"
        return f"Due in {days_left:.0f}d"

    @staticmethod
    def _resource_summary(cpu: Optional[float], mem: Optional[float]) -> str:
        parts = []
        if cpu is not None:
            parts.append(f"CPU {cpu:.0f}%")
        if mem is not None:
            parts.append(f"memory {mem:.0f}%")
        return ", ".join(parts)


_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
