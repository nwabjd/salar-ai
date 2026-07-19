from io import BytesIO


def test_upload_list_and_search_text_document(client, auth_headers):
    upload = client.post(
        "/api/documents",
        headers=auth_headers,
        data={"project_id": ""},
        files={"file": ("architecture.txt", BytesIO(b"SALAR uses one shared FastAPI backend."), "text/plain")},
    )
    assert upload.status_code == 201
    assert upload.json()["filename"] == "architecture.txt"

    listing = client.get("/api/documents", headers=auth_headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    search = client.get("/api/documents/search", params={"q": "FastAPI"}, headers=auth_headers)
    assert search.status_code == 200
    assert search.json()[0]["filename"] == "architecture.txt"
    assert "FastAPI" in search.json()[0]["snippet"]


def test_rejects_unsupported_document_type(client, auth_headers):
    response = client.post(
        "/api/documents",
        headers=auth_headers,
        files={"file": ("payload.exe", BytesIO(b"nope"), "application/octet-stream")},
    )
    assert response.status_code == 415
