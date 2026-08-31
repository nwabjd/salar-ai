def test_project_crud_with_goals(client, auth_headers):
    created = client.post(
        "/api/projects",
        json={"name": "Launch", "description": "Ship the app", "goals": ["final review", "ship"], "status": "active"},
        headers=auth_headers,
    )
    assert created.status_code == 201
    project = created.json()
    assert project["name"] == "Launch"
    assert project["goals"] == ["final review", "ship"]

    listing = client.get("/api/projects", headers=auth_headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    detail = client.get(f"/api/projects/{project['id']}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["description"] == "Ship the app"

    updated = client.patch(
        f"/api/projects/{project['id']}",
        json={"name": "Launch", "description": "Ship", "status": "completed"},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "completed"

    deleted = client.delete(f"/api/projects/{project['id']}", headers=auth_headers)
    assert deleted.status_code == 204
    assert client.get("/api/projects", headers=auth_headers).json() == []


def test_project_status_and_search_filters(client, auth_headers):
    client.post("/api/projects", json={"name": "Active work", "description": "ongoing"}, headers=auth_headers)
    client.post(
        "/api/projects",
        json={"name": "Old project", "description": "finished work", "status": "archived"},
        headers=auth_headers,
    )

    active = client.get("/api/projects", params={"status_filter": "active"}, headers=auth_headers)
    assert [p["name"] for p in active.json()] == ["Active work"]

    search = client.get("/api/projects", params={"search": "finished"}, headers=auth_headers)
    assert [p["name"] for p in search.json()] == ["Old project"]