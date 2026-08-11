from app.services.searcher import search_web, search_web_results


class FakeDDGS:
    def text(self, query, max_results):
        assert query == "Gemini Live API"
        assert max_results == 2
        return [
            {
                "title": "Live API",
                "body": "Official bidirectional streaming documentation.",
                "href": "https://ai.google.dev/api/live",
                "date": "2026-08-01",
            },
            {
                "title": "Capabilities",
                "body": "Live API capability guide.",
                "href": "https://ai.google.dev/gemini-api/docs/live-api/capabilities",
            },
        ]


def test_search_web_results_returns_normalized_evidence(monkeypatch):
    monkeypatch.setattr("app.services.searcher.DDGS", FakeDDGS)

    assert search_web_results("Gemini Live API", 2) == [
        {
            "title": "Live API",
            "snippet": "Official bidirectional streaming documentation.",
            "url": "https://ai.google.dev/api/live",
            "published_at": "2026-08-01",
        },
        {
            "title": "Capabilities",
            "snippet": "Live API capability guide.",
            "url": "https://ai.google.dev/gemini-api/docs/live-api/capabilities",
            "published_at": None,
        },
    ]


def test_search_web_preserves_text_contract(monkeypatch):
    monkeypatch.setattr("app.services.searcher.DDGS", FakeDDGS)

    result = search_web("Gemini Live API", 2)

    assert "Live API: Official bidirectional streaming documentation. (https://ai.google.dev/api/live)" in result
    assert "Capabilities: Live API capability guide. (https://ai.google.dev/gemini-api/docs/live-api/capabilities)" in result
