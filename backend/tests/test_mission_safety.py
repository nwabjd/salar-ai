# tests/test_mission_safety.py
from app.services.missions.safety import classify_tool

SAFE_TOOLS = [
    ("list_files", {}),
    ("read_file", {"path": "a.txt"}),
    ("search_files", {"q": "x"}),
    ("get_system_info", {}),
    ("get_current_time", {}),
    ("calendar_today", {}),
    ("calendar_upcoming", {}),
    ("list_tasks", {}),
    ("list_reminders", {}),
    ("search_knowledge", {"q": "x"}),
    ("browse_page", {"url": "https://x.com"}),
    ("get_monitor_stats", {}),
    ("get_battery", {}),
    ("get_disk_usage", {}),
    ("get_uptime", {}),
    ("network_info", {}),
    ("list_documents", {}),
    ("search_documents", {"q": "x"}),
    ("list_memories", {}),
    ("search_memories", {"q": "x"}),
    ("search_apps", {"q": "x"}),
]

CAUTION_TOOLS = [
    ("create_task", {"title": "do thing"}),
    ("set_reminder", {"title": "remind me"}),
    ("save_memory", {"title": "m", "content": "c"}),
    ("file_write", {"path": "a.txt", "content": "hi"}),
    ("write_file", {"path": "a.txt", "content": "hi"}),
    ("update_task", {"task_id": "x", "title": "y"}),
    ("set_task_status", {"task_id": "x", "status": "done"}),
    ("calendar_add_feed", {"url": "https://x.com/feed.ics"}),
    ("create_workspace", {"name": "ws"}),
    ("create_alert_rule", {"type": "x", "config": {}}),
]

DANGEROUS_TOOLS = [
    ("run_command", {"command": "rm -rf /tmp/junk"}),
    ("email_send", {"to": "a@b.com", "subject": "hi", "body": "hello"}),
    ("device_command", {"device_id": "d1", "command": "reboot"}),
    ("power_control", {"action": "shutdown"}),
    ("manage_process", {"action": "kill", "pid": 123}),
    ("code_run", {"language": "python", "code": "print(1)"}),
    ("delete_memory", {"memory_id": "m1"}),
    ("delete_task", {"task_id": "t1"}),
    ("delete_reminder", {"reminder_id": "r1"}),
    ("toggle_workflow", {"workflow_id": "w1"}),
]


def test_safe_tools():
    for tool, args in SAFE_TOOLS:
        assert classify_tool(tool, args) == "safe", f"{tool} should be safe"


def test_caution_tools():
    for tool, args in CAUTION_TOOLS:
        assert classify_tool(tool, args) == "caution", f"{tool} should be caution"


def test_dangerous_tools():
    for tool, args in DANGEROUS_TOOLS:
        assert classify_tool(tool, args) == "dangerous", f"{tool} should be dangerous"


def test_unknown_tool_is_dangerous():
    assert classify_tool("totally_fictional_tool", {}) == "dangerous"


def test_run_command_readonly_is_caution():
    assert classify_tool("run_command", {"command": "dir"}) == "caution"
    assert classify_tool("run_command", {"command": "echo hello"}) == "caution"
    assert classify_tool("run_command", {"command": "type file.txt"}) == "caution"
    assert classify_tool("run_command", {"command": "where python"}) == "caution"
