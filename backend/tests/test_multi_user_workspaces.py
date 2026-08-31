# backend/tests/test_multi_user_workspaces.py
import pytest


def test_user_profile_and_workspace_invite_flow(client, auth_headers):
    # 1. Check me endpoint
    me_resp = client.get("/api/users/me", headers=auth_headers)
    assert me_resp.status_code == 200
    profile = me_resp.json()
    assert "email" in profile
    assert "owned_workspaces" in profile

    # 2. Create a workspace
    ws_resp = client.post(
        "/api/workspaces",
        headers=auth_headers,
        json={"name": "Engineering Team", "icon": "🚀", "color": "#00FF00"},
    )
    assert ws_resp.status_code == 200
    ws = ws_resp.json()

    # 3. Invite a new user to the workspace
    invite_resp = client.post(
        "/api/users/invite",
        headers=auth_headers,
        json={"email": "alice@company.com", "workspace_id": ws["id"], "role": "admin"},
    )
    assert invite_resp.status_code == 201
    invited = invite_resp.json()
    assert invited["status"] == "ok"
    assert invited["user"]["email"] == "alice@company.com"

    # 4. List workspace members
    members_resp = client.get(f"/api/users/workspaces/{ws['id']}/members", headers=auth_headers)
    assert members_resp.status_code == 200
    members = members_resp.json()["members"]
    assert len(members) >= 2
    emails = [m["email"] for m in members]
    assert "alice@company.com" in emails

    # 5. List all users
    list_resp = client.get("/api/users/list", headers=auth_headers)
    assert list_resp.status_code == 200
    all_users = list_resp.json()["users"]
    assert any(u["email"] == "alice@company.com" for u in all_users)


def test_workspace_member_removal(client, auth_headers):
    ws = client.post("/api/workspaces", headers=auth_headers, json={"name": "Design Team"}).json()
    invited = client.post(
        "/api/users/invite",
        headers=auth_headers,
        json={"email": "bob@company.com", "workspace_id": ws["id"], "role": "member"},
    ).json()["user"]

    remove_resp = client.delete(
        f"/api/users/workspaces/{ws['id']}/members/{invited['id']}",
        headers=auth_headers,
    )
    assert remove_resp.status_code == 200
    assert remove_resp.json()["status"] == "removed"
