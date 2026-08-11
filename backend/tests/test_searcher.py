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


class EdgeCaseDDGS:
    def text(self, query, max_results):
        return [
            {
                "title": "  ",
                "body": "  ",
                "snippet": "  Snippet fallback  ",
                "url": "  https://example.com/fallback  ",
                "date": 20260801,
            },
            {"title": "Ignored", "href": " javascript:alert(1) "},
            {"title": "Ignored", "href": "/relative"},
            {"title": "Ignored", "href": "   "},
            {"title": "Ignored", "href": 42},
            None,
            "not a result",
        ]


class FailingDDGS:
    def text(self, query, max_results):
        raise RuntimeError("DDGS unavailable")


class UrlHardeningDDGS:
    def text(self, query, max_results):
        return [
            {
                "title": "Published fallback",
                "href": "https://example.com/published",
                "date": "  ",
                "published_at": " 2026-08-02 ",
            },
            {"href": "https://example\n.com/newline"},
            {"href": "https://example\t.com/tab"},
            {"href": "http:// /path"},
            {"href": "https://example.com:99999"},
            {"href": "https://example.com:not-a-port"},
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

    assert result == (
        "Live API: Official bidirectional streaming documentation. (https://ai.google.dev/api/live)\n"
        "Capabilities: Live API capability guide. (https://ai.google.dev/gemini-api/docs/live-api/capabilities)"
    )


def test_search_web_results_normalizes_fallbacks_and_skips_invalid_rows(monkeypatch):
    monkeypatch.setattr("app.services.searcher.DDGS", EdgeCaseDDGS)

    assert search_web_results("edge cases") == [
        {
            "title": "https://example.com/fallback",
            "snippet": "Snippet fallback",
            "url": "https://example.com/fallback",
            "published_at": "20260801",
        }
    ]


def test_search_web_returns_empty_values_when_ddgs_fails(monkeypatch):
    monkeypatch.setattr("app.services.searcher.DDGS", FailingDDGS)

    assert search_web_results("unavailable") == []
    assert search_web("unavailable") == ""


def test_search_web_results_uses_published_at_fallback_and_rejects_unsafe_urls(monkeypatch):
    monkeypatch.setattr("app.services.searcher.DDGS", UrlHardeningDDGS)

    assert search_web_results("URL hardening") == [
        {
            "title": "Published fallback",
            "snippet": "",
            "url": "https://example.com/published",
            "published_at": "2026-08-02",
        }
    ]
