from ddgs import DDGS
from typing import Dict, List, Optional
from urllib.parse import urlsplit


def _normalized_text(value: object) -> str:
    if value is None:
        return ""
    try:
        return str(value).strip()
    except (TypeError, ValueError):
        return ""


def _normalized_url(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    url = value.strip()
    if not url:
        return None
    try:
        parsed = urlsplit(url)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return url


def search_web_results(query: str, max_results: int = 5) -> List[Dict[str, Optional[str]]]:
    try:
        ddgs = DDGS()
        results = list(ddgs.text(query, max_results=max_results))
        normalized_results = []
        for result in results:
            if not isinstance(result, dict):
                continue
            url = _normalized_url(result.get("href")) or _normalized_url(result.get("url"))
            if url is None:
                continue
            title = _normalized_text(result.get("title")) or url
            snippet = _normalized_text(result.get("body")) or _normalized_text(result.get("snippet"))
            published_at = _normalized_text(result.get("date")) or None
            normalized_results.append(
                {
                    "title": title,
                    "snippet": snippet,
                    "url": url,
                    "published_at": published_at,
                }
            )
        return normalized_results
    except Exception:
        return []


def search_web(query: str, max_results: int = 5) -> str:
    results = search_web_results(query, max_results)
    return "\n".join(
        f"{result['title']}: {result['snippet']} ({result['url']})" for result in results
    )
