# backend/app/services/swarm.py
import json
import logging
from typing import Any, Dict, List

from ..models import AgentRun, AgentRunStep, token_id, utcnow

log = logging.getLogger(__name__)

AGENT_SPECS: Dict[str, Dict[str, Any]] = {
    "Researcher": {
        "description": "Finds and cross-checks information from the web.",
        "tools": ["browse_page", "browse_links", "read_article", "search_knowledge", "search_documents"],
        "signals": ["research", "find", "investigate", "compare", "sources", "look up", "search", "explain"],
    },
    "Coder": {
        "description": "Writes, fixes, and runs code.",
        "tools": ["run_command", "code_run", "file_read", "file_write", "list_files", "read_file", "write_file", "search_files"],
        "signals": ["code", "program", "build", "fix", "debug", "refactor", "script", "python", "function"],
    },
    "Browser": {
        "description": "Navigates and summarizes web pages.",
        "tools": ["browse_page", "browse_links", "read_article", "open_url"],
        "signals": ["browser", "website", "web page", "url", "download page", "form"],
    },
    "File Manager": {
        "description": "Organizes, renames, and summarizes files.",
        "tools": ["list_files", "file_list", "file_info", "file_read", "file_write", "file_search", "read_file", "write_file", "search_files"],
        "signals": ["file", "folder", "organize", "downloads", "document", "backup", "sort"],
    },
    "Vision": {
        "description": "Understands screenshots and images.",
        "tools": ["screenshot"],
        "signals": ["screenshot", "image", "screen", "vision", "look at", "what is wrong"],
    },
    "Email": {
        "description": "Reads, triages, and sends email.",
        "tools": ["email_read", "email_search", "email_unread", "email_send", "email_folders"],
        "signals": ["email", "inbox", "mail", "reply", "unread"],
    },
    "Calendar": {
        "description": "Manages schedules, tasks, and reminders.",
        "tools": ["calendar_today", "calendar_upcoming", "calendar_search", "calendar_events", "create_task", "update_task", "list_tasks", "set_reminder", "list_reminders", "update_reminder"],
        "signals": ["calendar", "schedule", "meeting", "appointment", "task", "reminder", "deadline"],
    },
    "System": {
        "description": "Monitors and controls the local system.",
        "tools": ["get_system_info", "get_monitor_stats", "get_uptime", "network_info", "list_processes", "manage_process", "get_battery", "get_disk_usage"],
        "signals": ["system", "cpu", "memory", "storage", "process", "status", "health", "uptime"],
    },
}

DEFAULT_AGENTS = ["Researcher", "System"]


class AgentSwarm:
    def __init__(self, db) -> None:
        self.db = db

    def decompose(self, goal: str) -> List[Dict[str, Any]]:
        """Choose specialized agents for a goal."""
        lowered = goal.lower()
        chosen: List[Dict[str, Any]] = []
        for name, spec in AGENT_SPECS.items():
            if any(sig in lowered for sig in spec["signals"]):
                chosen.append({"name": name, "description": spec["description"], "tools": spec["tools"]})
        for name in DEFAULT_AGENTS:
            if not any(a["name"] == name for a in chosen):
                spec = AGENT_SPECS[name]
                chosen.append({"name": name, "description": spec["description"], "tools": spec["tools"]})
        return chosen

    def create_run(self, user_id: str, goal: str, agents: List[Dict[str, Any]]) -> AgentRun:
        run = AgentRun(
            id=token_id(), user_id=user_id, kind="swarm",
            status="running",
            input_json=json.dumps({"goal": goal, "agents": [a["name"] for a in agents]}),
            created_at=utcnow(), updated_at=utcnow(),
        )
        self.db.add(run)
        self.db.flush()
        for i, agent in enumerate(agents, 1):
            self.db.add(AgentRunStep(
                id=token_id(), run_id=run.id, sequence=i,
                name=agent["name"], status="pending",
                detail_json=json.dumps({"description": agent["description"], "tools": agent["tools"]}),
                created_at=utcnow(),
            ))
        return run

    def agent_summary(self, run: AgentRun) -> Dict[str, Any]:
        steps = self.db.query(AgentRunStep).filter(AgentRunStep.run_id == run.id).order_by(AgentRunStep.sequence).all()
        return {
            "id": run.id,
            "kind": run.kind,
            "status": run.status,
            "input": json.loads(run.input_json or "{}"),
            "agents": [
                {"name": s.name, "status": s.status, "detail": json.loads(s.detail_json or "{}")}
                for s in steps
            ],
            "created_at": run.created_at.isoformat() if run.created_at else None,
        }
