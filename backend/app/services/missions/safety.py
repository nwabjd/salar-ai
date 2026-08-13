# backend/app/services/missions/safety.py
import re

_SAFE = {
    "list_files", "read_file", "search_files", "get_system_info", "get_current_time",
    "calendar_today", "calendar_upcoming", "calendar_events", "calendar_search",
    "list_tasks", "list_reminders", "search_knowledge", "list_knowledge",
    "browse_page", "read_article", "browse_links", "get_monitor_stats",
    "get_battery", "get_disk_usage", "get_uptime", "network_info",
    "list_documents", "search_documents", "list_memories", "search_memories",
    "list_workspaces", "list_alert_rules", "list_triggered_alerts", "list_workflow_runs",
    "search_apps", "clipboard", "file_list", "file_read", "file_info", "file_search",
    "calculate", "get_weather",
}

_CAUTION = {
    "create_task", "set_reminder", "save_memory", "file_write", "write_file",
    "update_task", "set_task_status", "update_reminder", "mark_reminder_done",
    "calendar_add_feed", "create_workspace", "create_alert_rule",
    "list_workflows", "run_workflow", "open_app", "open_url", "open_explorer",
    "set_volume", "set_brightness", "media_control", "window_control",
    "whatsapp_send", "send_notification", "create_workflow",
}

_DANGEROUS = {
    "run_command", "email_send", "device_command", "power_control",
    "manage_process", "code_run", "delete_memory", "delete_task",
    "delete_reminder", "screenshot",
}

_READONLY_CMD = re.compile(
    r"^\s*(dir|echo|type|where|whoami|hostname|date|time|tree|path|set|ver|systeminfo|tasklist|ipconfig|nslookup|netstat|ping|tracert)\b",
    re.IGNORECASE,
)


def classify_tool(tool: str, args: dict) -> str:
    if tool in _SAFE:
        return "safe"
    if tool in _CAUTION:
        return "caution"
    if tool in _DANGEROUS:
        if tool == "run_command":
            cmd = (args.get("command") or "").strip()
            if _READONLY_CMD.match(cmd):
                return "caution"
        return "dangerous"
    return "dangerous"
