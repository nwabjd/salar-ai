# backend/tests/test_files_upload.py
"""Upload sandboxing: filename sanitization, size cap, rename traversal."""
import pytest

from app.services.file_manager import FileManager


def _upload(client, headers, filename, content, path=""):
    return client.post(
        "/api/files/upload",
        headers=headers,
        params={"path": path},
        files={"file": (filename, content)},
    )


def test_upload_sanitizes_traversal_filename(client, exchange):
    headers = exchange("uploader@example.com")
    resp = _upload(client, headers, "../evil.txt", b"x")
    assert resp.status_code == 200
    body = resp.json()
    assert body["path"] == "evil.txt"  # stripped to a basename inside the sandbox

    me = client.get("/api/auth/me", headers=headers).json()
    root = client.app.state.settings.storage_dir / "users" / me["id"]
    assert (root / "evil.txt").exists()
    # escaped out of the user sandbox
    assert not (root.parent / "evil.txt").exists()


def test_upload_rejects_traversal_in_target_dir(client, exchange):
    headers = exchange("uploader@example.com")
    resp = _upload(client, headers, "ok.txt", b"x", path="../../escape")
    assert resp.status_code == 403


def test_upload_size_cap(client, exchange):
    headers = exchange("uploader@example.com")
    client.app.state.settings.max_upload_mb = 1
    resp = _upload(client, headers, "big.bin", b"x" * (2 * 1024 * 1024))
    assert resp.status_code == 413


def test_upload_dot_names_rejected(client, exchange):
    headers = exchange("uploader@example.com")
    for bad in (".", "..", "/", "\\"):
        resp = _upload(client, headers, bad, b"x")
        assert resp.status_code == 400


def test_rename_rejects_traversal(client, exchange):
    headers = exchange("uploader@example.com")
    me = client.get("/api/auth/me", headers=headers).json()
    fm = FileManager(root=str(client.app.state.settings.storage_dir / "users" / me["id"]))
    fm.write_file("notes.txt", "hi")

    result = fm.rename("notes.txt", "../escape.txt")
    assert "error" in result
    assert not (fm.root.parent / "escape.txt").exists()
    assert (fm.root / "notes.txt").exists()


def test_rename_within_root_still_works(client, exchange):
    headers = exchange("uploader@example.com")
    me = client.get("/api/auth/me", headers=headers).json()
    fm = FileManager(root=str(client.app.state.settings.storage_dir / "users" / me["id"]))
    fm.write_file("notes.txt", "hi")

    # "sub/../notes2.txt" resolves inside the root and must be allowed
    result = fm.rename("notes.txt", "sub/../notes2.txt")
    assert "error" not in result
    assert (fm.root / "notes2.txt").exists()