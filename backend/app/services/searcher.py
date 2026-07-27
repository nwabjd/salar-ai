from ddgs import DDGS


def search_web(query: str, max_results: int = 5) -> str:
    try:
        ddgs = DDGS()
        results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return ""
        lines = []
        for r in results:
            title = r.get("title", "")
            body = r.get("body", "")
            link = r.get("href", "")
            lines.append(f"{title}: {body} ({link})")
        return "\n".join(lines)
    except Exception:
        return ""
