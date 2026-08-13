# backend/app/services/guardian.py
import logging
import re
from typing import Any, Dict, List

from .intel.events import IntelEventStore

log = logging.getLogger(__name__)

_DESTRUCTIVE = re.compile(
    r"\b(rm\s+-rf|rmdir\s+/s|del\s+/[fqs]|format\s+[a-z]:|mkfs|diskpart|shutdown\s+/s|reg\s+delete)\b",
    re.IGNORECASE,
)
_DOWNLOAD_EXEC = re.compile(
    r"(curl|wget|Invoke-WebRequest|iwr|irm).{0,40}\|\s*(bash|sh|iex|powershell|zsh|python)",
    re.IGNORECASE,
)
_SENSITIVE_FILE = re.compile(r"(\.env|credential|password|secret|\.pem|\.key|api[_-]?key|token)", re.IGNORECASE)


class GuardianAnalyzer:
    def analyze(self, tool: str, args: Dict[str, Any]) -> List[Dict[str, str]]:
        flags: List[Dict[str, str]] = []
        if tool in ("run_command", "code_run"):
            cmd = str(args.get("command") or args.get("code") or "")
            if _DESTRUCTIVE.search(cmd):
                flags.append({"severity": "critical", "reason": "Destructive command pattern detected"})
            if _DOWNLOAD_EXEC.search(cmd):
                flags.append({"severity": "critical", "reason": "Download-and-execute pattern detected"})
        if tool in ("power_control", "device_command"):
            action = str(args.get("action") or args.get("command") or "").lower()
            if any(k in action for k in ("shutdown", "reboot", "restart", "sleep", "hibernate")):
                flags.append({"severity": "critical", "reason": "Power or device control requested"})
        if tool in ("file_write", "write_file"):
            path = str(args.get("path") or "")
            if _SENSITIVE_FILE.search(path):
                flags.append({"severity": "warning", "reason": "Overwriting a sensitive file"})
        if tool == "email_send":
            flags.append({"severity": "warning", "reason": "Outbound email sent"})
        if tool == "manage_process":
            action = str(args.get("action") or "").lower()
            if action in ("kill", "terminate", "stop"):
                flags.append({"severity": "warning", "reason": "Process termination"})
        if tool == "read_file":
            path = str(args.get("path") or "")
            if _SENSITIVE_FILE.search(path):
                flags.append({"severity": "info", "reason": "Credential file accessed"})
        if tool == "screenshot":
            flags.append({"severity": "info", "reason": "Screen capture taken"})
        return flags

    def flag_and_record(self, db, user_id: str, tool: str, args: Dict[str, Any], source: str):
        events = []
        store = IntelEventStore(db)
        for flag in self.analyze(tool, args):
            event = store.record(
                user_id=user_id,
                kind="guardian",
                severity=flag["severity"],
                title=f"Guardian: {flag['reason']}",
                summary=f"Tool '{tool}' triggered: {flag['reason']}",
                source=source,
                detail={"tool": tool, "args": args},
                evidence=[{"rule": flag["reason"]}],
            )
            events.append(event)
        return events
