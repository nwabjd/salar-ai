# backend/app/services/world_model/ingest.py
"""WorldIngestor — translates raw observations into world-graph updates.

This is the bridge between the messy real world (tool results, core-bus
events, calendar entries, emails, device heartbeats) and the structured
world graph. Each `ingest_*` method is small and deterministic; higher-value
extraction (entity linking, canonical names) can be layered on later.
"""

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from ...models import utcnow

log = logging.getLogger(__name__)

FILE_PATH_RE = re.compile(r"(?:^|[\"' ])([a-zA-Z0-9_./\\-]+\.[a-zA-Z0-9]{1,8})(?:[\"' ]|$)")
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


class WorldIngestor:
    """Stateless rules that turn observations into graph mutations."""

    def __init__(self, graph) -> None:
        self.graph = graph

    # ---------------- generic observation ----------------

    def ingest(
        self,
        user_id: str,
        *,
        source: str,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = payload or {}
        produced: Dict[str, Any] = {"source": source, "event_type": event_type, "entities": []}

        if event_type == "tool":
            produced["entities"] = self.ingest_tool(user_id, payload, source=source)
        elif event_type in ("calendar", "calendar_event"):
            produced["entities"] = [self.ingest_calendar_event(user_id, payload)]
        elif event_type in ("email", "email_message"):
            produced["entities"] = self.ingest_email(user_id, payload, source=source)
        elif event_type in ("device", "device_heartbeat"):
            produced["entities"] = [self.ingest_device(user_id, payload)]
        elif event_type in ("core_event",):
            produced["entities"] = self.ingest_core_event(user_id, payload, source=source)
        elif event_type == "memory":
            produced["entities"] = [self.ingest_memory(user_id, payload)]
        else:
            produced["entities"] = [self.ingest_generic(user_id, payload)]

        # Journal provenance for everything we touched.
        for eid in produced["entities"]:
            self.graph.journal(user_id, source=source, event_type=event_type, entity_id=eid, payload=payload)
        return produced

    # ---------------- tool observations ----------------

    def ingest_tool(self, user_id: str, payload: Dict[str, Any], *, source: str = "tool") -> List[str]:
        tool = str(payload.get("tool") or payload.get("name") or "").lower()
        args = payload.get("args") or {}
        result = payload.get("result") or {}
        produced: List[str] = []

        if tool in ("open_app", "launch_app", "start_app"):
            app = str(args.get("app") or args.get("name") or "").strip()
            if app:
                e = self.graph.upsert_entity(
                    user_id, "app", app.lower(), name=app, props={"open": True},
                    source=source, ttl_seconds=12 * 3600,
                )
                produced.append(e.id)
                path = args.get("path") or args.get("file") or args.get("cwd")
                if path:
                    file_id = self._link_file(user_id, path, source)
                    if file_id:
                        self.graph.relate(user_id, "app", app.lower(), "has_open", "file", _file_key(path),
                                          source=source, ttl_seconds=12 * 3600)
                        produced.append(file_id)

        elif tool in ("open_url", "browse", "fetch", "read_article", "extract_links"):
            url = str(args.get("url") or args.get("link") or "").strip()
            if url:
                e = self.graph.upsert_entity(user_id, "webpage", url, name=url,
                                             props={"url": url}, source=source, ttl_seconds=24 * 3600)
                produced.append(e.id)

        elif tool in ("write_file", "create_file", "append_file"):
            path = str(args.get("path") or args.get("file") or "").strip()
            if path:
                produced.append(self._link_file(user_id, path, source, mode="write"))

        elif tool in ("read_file", "open_file", "list_dir"):
            path = str(args.get("path") or args.get("file") or "").strip()
            if path:
                produced.append(self._link_file(user_id, path, source, mode="read"))

        elif tool in ("run_command", "execute_command", "shell", "bash", "powershell"):
            command = str(args.get("command") or args.get("cmd") or args.get("shell") or "")[:400]
            if command:
                e = self.graph.upsert_entity(user_id, "command", command,
                                             name=command[:120], props={"command": command},
                                             source=source, ttl_seconds=24 * 3600)
                produced.append(e.id)
                status = result.get("status") or result.get("exit_code")
                if status and str(status) not in ("0", "success", "SUCCESS", "ok", "OK", "None"):
                    self.graph.upsert_entity(user_id, "command", command,
                                             name=command[:120],
                                             props={"command": command, "status": "failed", "exit_code": str(status)},
                                             source=source, ttl_seconds=24 * 3600)
                    self.graph.upsert_entity(user_id, "build", command,
                                             name="Command failed", props={"status": "failed", "exit_code": str(status)},
                                             source=source, ttl_seconds=24 * 3600)

        elif tool in ("send_email", "send_whatsapp", "send_message", "email"):
            recipient = str(args.get("to") or args.get("recipient") or args.get("number") or "").strip()
            if recipient:
                produced.append(self._link_person(user_id, recipient, source))

        elif tool in ("add_event", "create_event", "schedule", "add_reminder", "set_reminder"):
            title = str(args.get("title") or args.get("summary") or args.get("text") or "")[:200]
            due = args.get("due") or args.get("when") or args.get("date") or args.get("time")
            if title:
                e = self.graph.upsert_entity(
                    user_id, "event", title, name=title,
                    props={"due": self._iso(due)} if due else {},
                    source=source, ttl_seconds=14 * 24 * 3600,
                )
                produced.append(e.id)

        return [eid for eid in produced if eid]

    # ---------------- source observations ----------------

    def ingest_calendar_event(self, user_id: str, payload: Dict[str, Any]) -> Optional[str]:
        title = str(payload.get("title") or payload.get("summary") or "").strip()[:200]
        if not title:
            return None
        e = self.graph.upsert_entity(
            user_id, "event", title, name=title,
            props={
                "start": self._iso(payload.get("start") or payload.get("start_time")),
                "end": self._iso(payload.get("end") or payload.get("end_time")),
                "calendar": payload.get("calendar") or "",
            },
            source="calendar",
            ttl_seconds=14 * 24 * 3600,
        )
        return e.id

    def ingest_email(self, user_id: str, payload: Dict[str, Any], *, source: str = "email") -> List[str]:
        produced: List[str] = []
        sender = str(payload.get("from") or payload.get("sender") or "").strip()
        recipient = str(payload.get("to") or "").strip()
        subject = str(payload.get("subject") or "").strip()[:200]
        for addr in (sender, recipient):
            if addr:
                pid = self._link_person(user_id, addr, source)
                if pid:
                    produced.append(pid)
        if subject:
            e = self.graph.upsert_entity(user_id, "email", f"{sender or '?'}:{subject}",
                                         name=subject, props={"from": sender, "to": recipient},
                                         source=source, ttl_seconds=7 * 24 * 3600)
            produced.append(e.id)
            if sender:
                self.graph.relate(user_id, "email", f"{sender or '?'}:{subject}", "from", "person", _email_key(sender),
                                  source=source, ttl_seconds=7 * 24 * 3600)
        return [eid for eid in produced if eid]

    def ingest_device(self, user_id: str, payload: Dict[str, Any]) -> Optional[str]:
        name = str(payload.get("name") or payload.get("device_name") or "device").strip()
        key = str(payload.get("id") or payload.get("device_id") or name).strip().lower()
        e = self.graph.upsert_entity(
            user_id, "device", key, name=name,
            props={
                "cpu": payload.get("cpu"),
                "memory": payload.get("memory"),
                "platform": payload.get("platform") or "",
                "status": payload.get("status") or "online",
            },
            source="device",
            ttl_seconds=15 * 60,
        )
        return e.id

    def ingest_core_event(self, user_id: str, payload: Dict[str, Any], *, source: str = "core") -> List[str]:
        produced: List[str] = []
        event_type = str(payload.get("type") or payload.get("event_type") or "")
        if event_type in ("TASK_COMPLETED", "TASK_FAILED", "TASK_STARTED", "VERIFICATION_FAILED"):
            kind = "run" if "run" in event_type.lower() else "job"
            key = str(payload.get("task_id") or payload.get("run_id") or event_type)
            status = "failed" if "FAILED" in event_type else "completed" if "COMPLETED" in event_type else "running"
            e = self.graph.upsert_entity(user_id, kind, key,
                                         name=str(payload.get("request") or payload.get("description") or event_type)[:200],
                                         props={"status": status, "trace_id": payload.get("trace_id")},
                                         source=source, ttl_seconds=24 * 3600)
            produced.append(e.id)
            if status == "failed" and "trace_id" in payload:
                build = self.graph.upsert_entity(user_id, "build", str(payload["trace_id"]),
                                                 name="Build failed", props={"status": "failed"},
                                                 source=source, ttl_seconds=24 * 3600)
                produced.append(build.id)
        return [eid for eid in produced if eid]

    def ingest_memory(self, user_id: str, payload: Dict[str, Any]) -> Optional[str]:
        title = str(payload.get("title") or "").strip()[:200]
        if not title:
            return None
        kind = str(payload.get("kind") or "memory")
        entity_type = "project" if kind == "project" else "memory"
        e = self.graph.upsert_entity(
            user_id, entity_type, title, name=title,
            summary=str(payload.get("content") or "")[:500],
            source="memory",
        )
        return e.id

    def ingest_generic(self, user_id: str, payload: Dict[str, Any]) -> Optional[str]:
        title = str(payload.get("title") or payload.get("name") or "")[:200]
        if not title:
            return None
        e = self.graph.upsert_entity(user_id, str(payload.get("type") or "fact"), title,
                                     name=title, summary=str(payload.get("summary") or "")[:500],
                                     source=str(payload.get("source") or "generic"))
        return e.id

    # ---------------- entity-linking helpers ----------------

    def _link_file(self, user_id: str, path: str, source: str, *, mode: str = "read") -> Optional[str]:
        path = str(path).strip()
        if not path:
            return None
        key = _file_key(path)
        e = self.graph.upsert_entity(
            user_id, "file", key, name=path.split("/")[-1].split("\\")[-1],
            props={"path": path, "mode": mode},
            source=source, ttl_seconds=30 * 24 * 3600,
        )
        return e.id

    def _link_person(self, user_id: str, identifier: str, source: str) -> Optional[str]:
        identifier = str(identifier).strip()
        if not identifier:
            return None
        email = EMAIL_RE.search(identifier)
        if email:
            addr = email.group(0).lower()
            e = self.graph.upsert_entity(user_id, "person", addr, name=addr,
                                         props={"email": addr}, source=source, ttl_seconds=30 * 24 * 3600)
            return e.id
        e = self.graph.upsert_entity(user_id, "person", identifier.lower(), name=identifier,
                                     source=source, ttl_seconds=30 * 24 * 3600)
        return e.id

    @staticmethod
    def _iso(value: Any) -> str:
        if not value:
            return ""
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)[:40]


def _file_key(path: str) -> str:
    return str(path).strip().lower()


def _email_key(addr: str) -> str:
    m = EMAIL_RE.search(str(addr))
    return m.group(0).lower() if m else str(addr).lower().strip()
