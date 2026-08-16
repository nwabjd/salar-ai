# backend/app/services/world_model/actions.py
"""SituationActionPlanner — suggests deterministic action plans to resolve situations.

This service bridges Situations and Tools. It doesn't execute anything; it
proposes a list of ToolCalls that the user or agent can trigger.
"""

import hashlib
import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# Tools considered safe to execute without explicit confirmation.
_SAFE_TOOLS = {
    "list_files", "read_file", "file_list", "file_read", "file_info", "file_search",
    "get_current_time", "get_system_info", "screenshot",
    "email_search", "email_read", "email_folders", "email_unread",
    "calendar_events", "calendar_today", "calendar_upcoming", "calendar_search",
    "whatsapp_list_chats", "whatsapp_read", "whatsapp_search",
    "list_devices", "list_tasks", "list_reminders", "list_knowledge",
    "search_knowledge", "world_simulate", "world_situations",
    "task_stats", "browse_page", "read_article", "browse_links",
    "send_notification", "whatsapp_send",
}


def _risk_level(tool_calls: List[Dict[str, Any]]) -> str:
    """Classify the safety level of a list of tool calls."""
    for tc in tool_calls:
        name = tc.get("name", "")
        if name in _SAFE_TOOLS:
            continue
        if name == "run_command":
            return "high"
        if name == "write_file":
            return "medium"
        if name == "email_send":
            return "medium"
        if name in ("open_app", "open_url", "device_command"):
            return "medium"
        return "high"
    return "low"


class ActionPlan:
    def __init__(
        self,
        *,
        situation_kind: str,
        title: str,
        description: str,
        tool_calls: List[Dict[str, Any]],
        severity: str = "normal",
    ) -> None:
        self.situation_kind = situation_kind
        self.title = title
        self.description = description
        self.tool_calls = tool_calls
        self.severity = severity
        self.id = hashlib.sha1(f"{situation_kind}:{title}".encode()).hexdigest()[:16]
        self.risk = _risk_level(tool_calls)
        self.score = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "situation_kind": self.situation_kind,
            "title": self.title,
            "description": self.description,
            "tool_calls": self.tool_calls,
            "risk": self.risk,
            "severity": self.severity,
            "score": round(self.score, 3),
        }


class SituationActionPlanner:
    def __init__(self, db) -> None:
        self.db = db

    def propose_actions(self, user_id: str, situations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        plans: List[ActionPlan] = []

        for sit in situations:
            kind = sit.get("kind")
            props = sit.get("props", {})
            entity_ids = sit.get("entity_ids", [])

            if kind == "failing_build":
                plans.append(ActionPlan(
                    situation_kind=kind,
                    title="Investigate build failure",
                    description="Read build logs and check recent changes",
                    tool_calls=[
                        {"name": "run_command", "args": {"command": "git status"}},
                        {"name": "run_command", "args": {"command": "git log -n 5"}},
                    ],
                    severity="high",
                ))

            elif kind == "collaborator_activity":
                channel = props.get("channel")
                person_name = sit["title"].split(" reached out")[0]
                if channel == "whatsapp":
                    plans.append(ActionPlan(
                        situation_kind=kind,
                        title=f"Reply to {person_name} (WhatsApp)",
                        description="Send a quick response via WhatsApp",
                        tool_calls=[
                            {"name": "whatsapp_send", "args": {"text": "Hey, I'm looking into it now.", "to": props.get("jid") or entity_ids[1] if len(entity_ids) > 1 else ""}}
                        ],
                    ))
                elif channel == "email":
                    plans.append(ActionPlan(
                        situation_kind=kind,
                        title=f"Reply to {person_name} (Email)",
                        description="Draft a short reply email",
                        tool_calls=[
                            {"name": "email_send", "args": {"to": props.get("from") or entity_ids[1] if len(entity_ids) > 1 else "", "subject": f"Re: {sit['summary']}", "body": "I've received your email and am working on it."}}
                        ],
                    ))

            elif kind == "direct_message":
                person_name = sit["title"].replace("New message from ", "")
                channel = props.get("channel", "unknown")
                plans.append(ActionPlan(
                    situation_kind=kind,
                    title=f"Check message from {person_name}",
                    description=f"Open the latest message via {channel}",
                    tool_calls=[],
                ))

            elif kind == "task_due":
                task_id = props.get("task_id", "")
                plans.append(ActionPlan(
                    situation_kind=kind,
                    title=sit["title"],
                    description=sit.get("summary", ""),
                    tool_calls=[],
                ))

            elif kind == "resource_pressure":
                plans.append(ActionPlan(
                    situation_kind=kind,
                    title="Optimize resources",
                    description="List running processes to identify memory/CPU hogs",
                    tool_calls=[
                        {"name": "run_command", "args": {"command": "tasklist" if "windows" in sit["title"].lower() else "top -n 1"}}
                    ],
                ))

            elif kind == "deadline_pressure":
                plans.append(ActionPlan(
                    situation_kind=kind,
                    title="Check project status",
                    description="Review open tasks and files for this project",
                    tool_calls=[
                        {"name": "list_files", "args": {"path": props.get("repo_path") or "."}}
                    ],
                ))

        if not plans:
            return []

        # Self-evolution: rank proposed actions by learned success score so
        # actions that historically resolve a situation get proposed first.
        try:
            from .evolution import EvolutionEngine
            evolution = EvolutionEngine(self.db)
            for p in plans:
                p.score = evolution.score_for(user_id, p.situation_kind, p.title)
        except Exception as error:
            log.warning("Policy scoring unavailable: %s", type(error).__name__)
            for p in plans:
                p.score = 0.0

        ordered = sorted(plans, key=lambda p: p.score, reverse=True)
        return [p.to_dict() for p in ordered]
