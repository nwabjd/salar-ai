import asyncio
import inspect
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from ..searcher import search_web_results
from .contracts import AgentResult, EvidenceSource, utc_iso
from .safe_fetch import SafePublicFetcher
from .urls import canonical_hostname, canonical_public_url


def _normalized_text(value: object) -> str:
    if value is None:
        return ""
    try:
        return re.sub(r"\s+", " ", str(value)).strip()
    except (TypeError, ValueError):
        return ""


def _public_web_url(value: object) -> bool:
    return canonical_public_url(value) is not None


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
        fetcher: Optional[SafePublicFetcher] = None,
        search_timeout: float = 8.0,
        page_timeout: float = 10.0,
        overall_timeout: float = 20.0,
    ) -> None:
        self.search = search or search_web_results
        self.fetcher = fetcher or SafePublicFetcher(timeout=min(float(page_timeout), 8.0))
        self.read_page = read_page or self.fetcher.fetch_page
        self.now = now or utc_iso
        self.search_timeout = max(0.001, float(search_timeout))
        self.page_timeout = max(0.001, float(page_timeout))
        self.overall_timeout = max(0.001, float(overall_timeout))

    async def run(self, query: str) -> AgentResult:
        try:
            return await asyncio.wait_for(self._run(query), timeout=self.overall_timeout)
        except asyncio.TimeoutError:
            return self._search_failure("Overall research timed out.")

    async def _run(self, query: str) -> AgentResult:
        try:
            # Sync defaults have lower-layer I/O timeouts. Cancelling to_thread
            # cannot kill a Python worker, but it does bound this orchestration.
            raw_results = await asyncio.wait_for(
                _call_in_worker(self.search, query, 6),
                timeout=self.search_timeout,
            )
        except asyncio.TimeoutError:
            return self._search_failure("Search timed out.")
        except Exception as exc:
            return self._search_failure(f"Search failed: {str(exc) or exc.__class__.__name__}")

        if not isinstance(raw_results, (list, tuple)) or not raw_results:
            return self._search_failure("Search returned no results.")

        candidates: List[Dict[str, Any]] = []
        seen_urls = set()
        for raw in raw_results:
            if not isinstance(raw, dict):
                continue
            url = canonical_public_url(_normalized_text(raw.get("url") or raw.get("href")))
            if url is None or url in seen_urls:
                continue
            seen_urls.add(url)
            candidates.append(
                {
                    "title": _normalized_text(raw.get("title")) or url,
                    "url": url,
                    "snippet": _normalized_text(raw.get("snippet") or raw.get("body")),
                    "publisher": canonical_hostname(url),
                    "published_at": _normalized_text(raw.get("published_at") or raw.get("date")) or None,
                }
            )
            if len(candidates) == 6:
                break

        if not candidates:
            return self._search_failure("Search returned no safe public-web results.")

        reads = await asyncio.gather(
            *(
                asyncio.wait_for(
                    _call_in_worker(self.read_page, candidate["url"]),
                    timeout=self.page_timeout,
                )
                for candidate in candidates[:3]
            ),
            return_exceptions=True,
        )
        opened_results = list(reads) + [None] * (len(candidates) - len(reads))
        retrieved_at = self._retrieved_at()
        evidence_by_url = {}

        for candidate, opened in zip(candidates, opened_results):
            opened_text = ""
            final_url = None
            if not isinstance(opened, BaseException) and isinstance(opened, dict):
                if opened.get("status") == 200:
                    opened_text = _normalized_text(opened.get("text"))
                    final_url = canonical_public_url(opened.get("url") or candidate["url"])
            successfully_opened = len(opened_text) >= 120 and final_url is not None
            evidence_url = final_url if successfully_opened else candidate["url"]
            if successfully_opened:
                excerpt = opened_text[:600]
                confidence = "high"
            else:
                excerpt = candidate["snippet"] or "Page content could not be verified."
                confidence = "low"
            item = EvidenceSource(
                title=candidate["title"],
                url=evidence_url,
                excerpt_summary=excerpt,
                publisher=canonical_hostname(evidence_url),
                published_at=candidate["published_at"],
                confidence=confidence,
                retrieved_at=retrieved_at,
                evidence_kind="opened_page" if successfully_opened else "search_only",
            )
            existing = evidence_by_url.get(evidence_url)
            if existing is None or (existing.evidence_kind == "search_only" and successfully_opened):
                evidence_by_url[evidence_url] = item

        evidence = list(evidence_by_url.values())
        opened_publishers = {
            item.publisher
            for item in evidence
            if item.evidence_kind == "opened_page" and item.confidence == "high"
        }
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
