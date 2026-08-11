from ddgs import DDGS
from typing import Dict, List, Optional


def search_web_results(query: str, max_results: int = 5) -> List[Dict[str, Optional[str]]]:
    try:
        ddgs = DDGS()
        results = list(ddgs.text(query, max_results=max_results))
        normalized_results = []
        for result in results:
            if not isinstance(result, dict):
                continue
            url = result.get("href")
            if not url:
                continue
            normalized_results.append(
                {
                    "title": str(result.get("title") or ""),
                    "snippet": str(result.get("body") or ""),
                    "url": str(url),
                    "published_at": result.get("date") or None,
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
