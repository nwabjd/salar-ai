def test_memory_crud_and_layer_filter(client, auth_headers):
    created = client.post(
        "/api/memories",
        json={"title": "Interface preference", "content": "Use exact component colors", "layer": "preference"},
        headers=auth_headers,
    )
    assert created.status_code == 201
    memory_id = created.json()["id"]

    listing = client.get("/api/memories?layer=preference", headers=auth_headers)
    assert [item["id"] for item in listing.json()] == [memory_id]

    updated = client.patch(
        f"/api/memories/{memory_id}",
        json={"title": "Visual preference", "content": "Keep supplied palettes unchanged", "layer": "preference"},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Visual preference"

    deleted = client.delete(f"/api/memories/{memory_id}", headers=auth_headers)
    assert deleted.status_code == 204
    assert client.get("/api/memories", headers=auth_headers).json() == []


def test_project_can_be_created_and_listed(client, auth_headers):
    created = client.post(
        "/api/projects",
        json={"name": "SALAR", "description": "Private assistant"},
        headers=auth_headers,
    )
    assert created.status_code == 201
    projects = client.get("/api/projects", headers=auth_headers).json()
    assert projects[0]["name"] == "SALAR"
