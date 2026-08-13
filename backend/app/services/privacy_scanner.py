# backend/app/services/privacy_scanner.py
import json
import logging
import re
from typing import Any, Dict, List

from sqlalchemy import select

from ..models import ActionLog, Document, Memory

log = logging.getLogger(__name__)

SECRET_RE = re.compile(r"(password\s*[=:]\s*\S+|api[_-]?key\s*[=:]\s*\S+|secret\s*[=:]\s*\S+|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|token\s*[=:]\s*[A-Za-z0-9_-]{20,})", re.IGNORECASE)
PII_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b|\b\d{9,11}\b")


class PrivacyScanner:
    def __init__(self, db) -> None:
        self.db = db

    def scan_user(self, user_id: str) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        # ActionLogs
        for a in self.db.scalars(select(ActionLog).where(ActionLog.user_id == user_id)).all():
            hay = f"{a.args_json or ''} {a.result_json or ''}"
            self._check(hay, f"action:{a.tool}", findings)
        # Memories
        for m in self.db.scalars(select(Memory).where(Memory.user_id == user_id)).all():
            self._check(f"{m.title} {m.content}", f"memory:{m.id}", findings)
        # Documents
        for d in self.db.scalars(select(Document).where(Document.user_id == user_id)).all():
            self._check(d.extracted_text or "", f"document:{d.filename}", findings)
        return findings

    def _check(self, text: str, source: str, findings: List[Dict[str, Any]]):
        if not text:
            return
        if SECRET_RE.search(text):
            findings.append({"source": source, "severity": "critical", "detail": "Possible secret or credential exposed in plaintext."})
        pii = PII_RE.findall(text)
        if len(pii) >= 2:
            findings.append({"source": source, "severity": "warning", "detail": f"Possible PII detected ({len(pii)} matches)."})

    def scan_report(self, user_id: str) -> Dict[str, Any]:
        findings = self.scan_user(user_id)
        return {
            "findings": findings,
            "total": len(findings),
            "critical": sum(1 for f in findings if f["severity"] == "critical"),
            "warning": sum(1 for f in findings if f["severity"] == "warning"),
        }
