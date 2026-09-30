def test_health_reports_service_readiness(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "salar-backend",
        "version": "0.1.0",
    }


def test_cors_allows_configured_web_origin(client):
    response = client.options(
        "/api/health",
        headers={
            "Origin": "https://salar.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.headers["access-control-allow-origin"] == "https://salar.example.com"


def test_cors_blocks_arbitrary_origin(client):
    response = client.options(
        "/api/health",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_desktop_tauri_origins_in_default_settings():
    """Regression: the Tauri desktop app resolves origins from the webview
    (http://tauri.localhost on Windows, tauri:// elsewhere, and the known
    'null' quirk) — all must be allowed so desktop builds can chat."""
    from app.config import Settings

    origins = Settings().allowed_origins
    for origin in ("http://tauri.localhost", "https://tauri.localhost", "tauri://localhost", "null"):
        assert origin in origins, f"{origin} missing from default allowed_origins"

