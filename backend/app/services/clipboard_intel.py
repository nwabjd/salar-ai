# backend/app/services/clipboard_intel.py
import logging
import re
from typing import Any, Dict

log = logging.getLogger(__name__)

URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
FILE_RE = re.compile(r"^[A-Za-z]:\\|^/[A-Za-z]/|\.\w{2,5}$")


class ClipboardIntelligence:
    def inspect(self) -> Dict[str, Any]:
        """Return clipboard snapshot + classification."""
        try:
            import pyperclip
            text = pyperclip.paste()
        except Exception as exc:
            return {"status": "unavailable", "detail": str(exc)}
        return self.classify(text)

    def classify(self, text: str) -> Dict[str, Any]:
        text = (text or "").strip()
        if not text:
            return {"status": "ok", "kind": "empty", "content": "", "suggested_actions": []}
        kind = "text"
        if URL_RE.fullmatch(text):
            kind = "url"
        elif EMAIL_RE.fullmatch(text):
            kind = "email"
        elif FILE_RE.search(text):
            kind = "file_path"
        elif text.isdigit():
            kind = "number"
        elif len(text) > 2000:
            kind = "long_text"
        suggested = {
            "url": ["Open in browser", "Summarize this page", "Save to knowledge"],
            "email": ["Compose email to this address", "Save as contact"],
            "file_path": ["Open file", "Summarize file", "Copy file path"],
            "text": ["Ask SALAR about this", "Translate", "Save to memory"],
            "number": ["Calculate", "Convert units"],
            "long_text": ["Summarize", "Extract key points", "Rewrite"],
            "empty": [],
        }[kind]
        return {"status": "ok", "kind": kind, "content": text[:2000], "suggested_actions": suggested}
