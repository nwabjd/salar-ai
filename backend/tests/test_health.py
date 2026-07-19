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

