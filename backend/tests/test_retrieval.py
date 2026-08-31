# tests/test_retrieval.py
import pytest


def test_retrieval_query_returns_results(client, auth_headers):
    # Upload a document so there's something to search.
    resp = client.post(
        "/api/documents",
        headers=auth_headers,
        files={"file": ("notes.txt", b"Solar panels convert sunlight into electricity.", "text/plain")},
    )
    assert resp.status_code == 201

    query = client.post(
        "/api/retrieval/query",
        headers=auth_headers,
        json={"query": "solar energy", "limit": 5},
    )
    assert query.status_code == 200
    body = query.json()
    assert body["count"] >= 1
    assert any(r["source"] == "document" for r in body["results"])


def test_retrieval_index_reports_count(client, auth_headers):
    idx = client.post("/api/retrieval/index", headers=auth_headers)
    assert idx.status_code == 200
    assert idx.json()["status"] == "ok"
    assert isinstance(idx.json()["indexed"], int)


def test_retrieval_keyword_fallback_on_empty_query(client, auth_headers):
    query = client.post(
        "/api/retrieval/query",
        headers=auth_headers,
        json={"query": "   ", "limit": 5},
    )
    assert query.status_code == 200
    assert query.json()["count"] == 0