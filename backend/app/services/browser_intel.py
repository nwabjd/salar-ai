# backend/app/services/browser_intel.py
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

log = logging.getLogger(__name__)


class BrowserIntelligence:
    def __init__(self, gemini=None) -> None:
        self._gemini = gemini

    async def fetch(self, url: str, *, max_chars: int = 15000) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                r = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (SALAR Research)"})
                r.raise_for_status()
                content_type = r.headers.get("content-type", "")
                if "html" not in content_type and "text" not in content_type:
                    return {"status": "ok", "url": url, "kind": "binary", "content_type": content_type, "length": len(r.content)}
                text = r.text[:max_chars]
                text = re.sub(r"<[^>]+>", " ", text)
                text = re.sub(r"\s+", " ", text).strip()
                return {"status": "ok", "url": url, "kind": "html", "content": text[:max_chars], "length": len(text)}
        except Exception as exc:
            return {"status": "error", "url": url, "detail": str(exc)}

    async def summarize(self, url: str) -> Dict[str, Any]:
        page = await self.fetch(url)
        if page.get("status") != "ok" or not page.get("content"):
            return {"status": "error", "detail": page.get("detail", "unable to fetch page"), "url": url}
        if self._gemini is None:
            return {"status": "ok", "url": url, "summary": page["content"][:500], "note": "no model configured"}
        text = await self._gemini.chat([
            {"role": "user", "content": f"Summarize this web page content in under 120 words:\n\n{page['content'][:12000]}"}
        ])
        return {"status": "ok", "url": url, "summary": text, "page": page["content"][:500]}
