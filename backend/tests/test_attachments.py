from io import BytesIO

def test_upload_attachment(client, auth_headers):
    response = client.post(
        "/api/attachments",
        headers=auth_headers,
        files={"file": ("test.png", BytesIO(b"fake image data"), "image/png")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "test.png"
    assert data["media_type"] == "image/png"
    assert "id" in data

def test_upload_attachment_unsupported(client, auth_headers):
    response = client.post(
        "/api/attachments",
        headers=auth_headers,
        files={"file": ("test.exe", BytesIO(b"executable"), "application/octet-stream")},
    )
    # Based on the implementation, it should return 415 or 400. 
    # My implementation in attachments.py doesn't have a restriction yet beyond what documents.py has?
    # Actually I should check my implementation of attachments.py.
    assert response.status_code == 415
