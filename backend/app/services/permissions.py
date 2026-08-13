# backend/app/services/permissions.py
import logging
from typing import Optional

from ..models import PermissionProfile as PermissionProfileModel, token_id, utcnow

log = logging.getLogger(__name__)

DEFAULT_LEVEL = "ask"
LEVELS = {"observe", "suggest", "ask", "autonomous"}
CATEGORIES = ["files", "camera", "microphone", "screen", "browser", "email", "calendar", "terminal", "system", "smart_home"]

_WRITE_TOOLS = {
    "file_write", "write_file", "save_memory", "delete_memory", "email_send",
    "create_task", "update_task", "set_task_status", "delete_task", "set_reminder",
    "update_reminder", "mark_reminder_done", "delete_reminder", "calendar_add_feed",
    "create_workspace", "create_workflow", "run_workflow", "toggle_workflow",
    "create_alert_rule", "send_notification", "whatsapp_send", "run_command",
    "code_run", "manage_process", "power_control", "device_command", "set_volume",
    "set_brightness", "media_control", "window_control", "open_app", "open_url",
    "open_explorer", "screenshot", "clipboard",
}

_TOOL_CATEGORY = {
    # files
    "file_info": "files", "file_list": "files", "file_read": "files",
    "file_search": "files", "file_write": "files", "list_files": "files",
    "read_file": "files", "search_files": "files", "write_file": "files",
    "list_documents": "files", "search_documents": "files",
    "save_memory": "files", "list_memories": "files", "search_memories": "files",
    "delete_memory": "files", "get_disk_usage": "files",
    "create_workspace": "files", "list_workspaces": "files",
    "list_knowledge": "files", "search_knowledge": "files",
    # calendar + tasks + reminders
    "calendar_add_feed": "calendar", "calendar_events": "calendar",
    "calendar_search": "calendar", "calendar_today": "calendar",
    "calendar_upcoming": "calendar", "create_task": "calendar",
    "update_task": "calendar", "set_task_status": "calendar",
    "delete_task": "calendar", "list_tasks": "calendar", "task_stats": "calendar",
    "set_reminder": "calendar", "list_reminders": "calendar",
    "update_reminder": "calendar", "mark_reminder_done": "calendar",
    "delete_reminder": "calendar",
    # email + whatsapp
    "email_folders": "email", "email_read": "email", "email_search": "email",
    "email_send": "email", "email_unread": "email",
    "whatsapp_list_chats": "email", "whatsapp_qr": "email",
    "whatsapp_read": "email", "whatsapp_search": "email", "whatsapp_send": "email",
    # browser
    "browse_links": "browser", "browse_page": "browser", "read_article": "browser",
    "open_url": "browser",
    # terminal
    "run_command": "terminal", "code_run": "terminal",
    "list_processes": "terminal", "manage_process": "terminal",
    # screen
    "screenshot": "screen", "window_control": "screen",
    # system
    "power_control": "system", "device_command": "system",
    "set_volume": "system", "set_brightness": "system",
    "media_control": "system", "open_app": "system", "open_explorer": "system",
    "get_system_info": "system", "get_uptime": "system", "get_battery": "system",
    "get_monitor_stats": "system", "network_info": "system",
    "send_notification": "system", "list_devices": "system",
    "get_current_time": "system", "get_weather": "system", "calculate": "system",
    "clipboard": "system",
    # workflows / alerts
    "create_workflow": "files", "run_workflow": "files", "toggle_workflow": "files",
    "list_workflows": "files", "create_alert_rule": "system",
    "list_alert_rules": "system", "list_triggered_alerts": "system",
    "search_apps": "system",
}


def category_for_tool(tool: str) -> str:
    return _TOOL_CATEGORY.get(tool, "system")


def is_write_tool(tool: str) -> bool:
    return tool in _WRITE_TOOLS


def valid_level(level: str) -> bool:
    return level in LEVELS


class PermissionProfile:
    def __init__(self, *, user_id: Optional[str] = None, levels: Optional[dict] = None) -> None:
        self.user_id = user_id
        self._levels = {cat: DEFAULT_LEVEL for cat in CATEGORIES}
        if levels:
            for cat, lvl in levels.items():
                if cat in self._levels and lvl in LEVELS:
                    self._levels[cat] = lvl

    def level_for(self, category: str) -> str:
        return self._levels.get(category, DEFAULT_LEVEL)

    def set_level(self, category: str, level: str) -> None:
        if category not in self._levels:
            raise ValueError(f"unknown category: {category}")
        if level not in LEVELS:
            raise ValueError(f"invalid level: {level}")
        self._levels[category] = level

    def levels(self) -> dict:
        return dict(self._levels)

    def save(self, db) -> None:
        row = PermissionProfileModel(
            id=token_id(), user_id=self.user_id, levels_json=self._to_json(), created_at=utcnow(), updated_at=utcnow(),
        )
        db.add(row)
        db.commit()

    def _to_json(self) -> str:
        import json
        return json.dumps(self._levels)

    @classmethod
    def for_user(cls, db, user_id: str) -> "PermissionProfile":
        row = db.query(PermissionProfileModel).filter(PermissionProfileModel.user_id == user_id).first()
        if row is None:
            return cls(user_id=user_id)
        return cls(user_id=user_id, levels=row.levels_dict())


def check_permission(profile: PermissionProfile, tool: str, args: dict) -> str:
    """Return "safe" (execute), "ask" (needs approval), or "denied" (never run)."""
    cat = category_for_tool(tool)
    level = profile.level_for(cat)
    from .missions.safety import classify_tool
    base = classify_tool(tool, args)
    if level == "autonomous":
        return "ask" if base == "dangerous" else "safe"
    if level == "ask":
        return "ask" if base == "dangerous" else "safe"
    if level == "suggest":
        return "denied"
    if level == "observe":
        return "denied" if is_write_tool(tool) else "safe"
    return "ask"
