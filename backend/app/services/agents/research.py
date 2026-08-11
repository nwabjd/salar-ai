import asyncio
import inspect
import ipaddress
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlsplit

from ..browser import WebBrowser
from ..searcher import search_web_results
from .contracts import AgentResult, EvidenceSource, utc_iso


def _normalized_text(value: object) -> str:
    if value is None:
        return ""
    try:
        return re.sub(r"\s+", " ", str(value)).strip()
    except (TypeError, ValueError):
        return ""


def _public_web_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    if any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in value):
        return False
    try:
        parsed = urlsplit(value.strip())
        hostname = parsed.hostname
        parsed.port
    except ValueError:
        return False
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc or not hostname:
        return False
    hostname = hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        return False
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return True
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


def _default_read_page(url: str) -> Dict[str, Any]:
    browser = WebBrowser()
    try:
        return browser.fetch_page(url)
    finally:
        browser.close()


async def _call_in_worker(callable_: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    if inspect.iscoroutinefunction(callable_):
        return await callable_(*args, **kwargs)
    value = await asyncio.to_thread(callable_, *args, **kwargs)
    if inspect.isawaitable(value):
        return await value
    return value


class ResearchAgent:
    def __init__(
        self,
        search: Optional[Callable[..., Any]] = None,
        read_page: Optional[Callable[[str], Any]] = None,
        now: Optional[Callable[[], Any]] = None,
    ) -> None:
        self.search = search or search_web_results
        self.read_page = read_page or _default_read_page
        self.now = now or utc_iso

    async def run(self, query: str) -> AgentResult:
        try:
            raw_results = await _call_in_worker(self.search, query, max_results=6)
        except Exception as exc:
            return self._search_failure(f"Search failed: {str(exc) or exc.__class__.__name__}")

        if not isinstance(raw_results, (list, tuple)) or not raw_results:
            return self._search_failure("Search returned no results.")

        candidates: List[Dict[str, Any]] = []
        for raw in raw_results:
            if not isinstance(raw, dict):
                continue
            url = _normalized_text(raw.get("url") or raw.get("href"))
            if not _public_web_url(url):
                continue
            candidates.append(
                {
                    "title": _normalized_text(raw.get("title")) or url,
                    "url": url,
                    "snippet": _normalized_text(raw.get("snippet") or raw.get("body")),
                    "publisher": _normalized_text(raw.get("publisher")) or (urlsplit(url).hostname or ""),
                    "published_at": _normalized_text(raw.get("published_at") or raw.get("date")) or None,
                }
            )
            if len(candidates) == 3:
                break

        if not candidates:
            return self._search_failure("Search returned no safe public-web results.")

        reads = await asyncio.gather(
            *(_call_in_worker(self.read_page, candidate["url"]) for candidate in candidates),
            return_exceptions=True,
        )
        retrieved_at = self._retrieved_at()
        evidence = []
        opened_publishers = set()

        for candidate, opened in zip(candidates, reads):
            opened_text = ""
            if not isinstance(opened, BaseException) and isinstance(opened, dict):
                if opened.get("status") == 200:
                    opened_text = _normalized_text(opened.get("text"))
            successfully_opened = len(opened_text) >= 120
            if successfully_opened:
                excerpt = opened_text[:600]
                confidence = "high"
                opened_publishers.add(candidate["publisher"].lower())
            else:
                excerpt = candidate["snippet"] or "Page content could not be verified."
                confidence = "low"
            evidence.append(
                EvidenceSource(
                    title=candidate["title"],
                    url=candidate["url"],
                    excerpt_summary=excerpt,
                    publisher=candidate["publisher"],
                    published_at=candidate["published_at"],
                    confidence=confidence,
                    retrieved_at=retrieved_at,
                )
            )

        opened_count = sum(item.confidence == "high" for item in evidence)
        if len(opened_publishers) >= 2:
            confidence = "high"
        elif opened_count >= 1:
            confidence = "medium"
        else:
            confidence = "low"

        return AgentResult(
            status="completed" if opened_count else "partial",
            summary=(
                f"Research found {len(evidence)} public source(s); "
                f"{opened_count} page(s) supplied verified readable content."
            ),
            evidence=evidence,
            confidence=confidence,
            suggested_next_action=(
                "Use the evidence excerpts and exact source URLs."
                if opened_count
                else "Retry research later or verify the search-result snippets directly."
            ),
        )

    def _retrieved_at(self) -> str:
        value = self.now()
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _search_failure(error: str) -> AgentResult:
        return AgentResult(
            status="failed",
            summary="Current web research is unavailable; no current claim was confirmed.",
            evidence=[],
            confidence="low",
            suggested_next_action="Retry the research later or provide a trusted public source to inspect.",
            error=error,
        )


__all__ = ["ResearchAgent"]
