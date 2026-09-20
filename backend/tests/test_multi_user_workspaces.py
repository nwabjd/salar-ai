# backend/tests/test_multi_user_workspaces.py
"""Workspace sharing authorization contract.

Non-admin users may invite others only into workspaces they own, may read
members only for workspaces they own or belong to, and can never remove
members. Listing all users (email enumeration) is admin-only. New accounts
created via invite never get a predictable default password.
"""
import pytest

from sqlalchemy import select

from app.models import User


def test_user_profile_and_owner_invite_flow(client, exchange):
    owner = exchange("alice@company.com")
    # 1. Check me endpoint
    me_resp = client.get("/api/users/me", headers=owner)
    assert me_resp.status_code == 200
    profile = me_resp.json()
    assert "email" in profile
    assert "owned_workspaces" in profile

    # 2. Non-admin owner creates a workspace
    ws_resp = client.post(
        "/api/workspaces",
        headers=owner,
        json={"name": "Engineering Team", "icon": "🚀", "color": "#00FF00"},
    )
    assert ws_resp.status_code == 200
    ws = ws_resp.json()

    # 3. Owner invites a new user into their own workspace
    invite_resp = client.post(
        "/api/users/invite",
        headers=owner,
        json={"email": "bob@company.com", "workspace_id": ws["id"], "role": "admin"},
    )
    assert invite_resp.status_code == 201
    invited = invite_resp.json()
    assert invited["status"] == "ok"
    assert invited["user"]["email"] == "bob@company.com"
    assert invited["user"]["is_admin"] is False

    # 4. Owner lists workspace members
    members_resp = client.get(f"/api/users/workspaces/{ws['id']}/members", headers=owner)
    assert members_resp.status_code == 200
    emails = [m["email"] for m in members_resp.json()["members"]]
    assert "bob@company.com" in emails

    # 5. A non-owner cannot list all users (email enumeration is admin-only)
    list_resp = client.get("/api/users/list", headers=owner)
    assert list_resp.status_code == 403


def test_only_workspace_owner_or_admin_can_invite(client, exchange):
    alice = exchange("alice@example.com")
    ws = client.post("/api/workspaces", headers=alice, json={"name": "Alice's workspace"}).json()
    stranger = exchange("stranger@example.com")

    # An account that does not own the workspace cannot inject a member into it
    resp = client.post(
        "/api/users/invite",
        headers=stranger,
        json={"email": "vic@example.com", "workspace_id": ws["id"]},
    )
    assert resp.status_code == 403

    # Creating accounts without a workspace is admin-only
    no_ws = client.post("/api/users/invite", headers=stranger, json={"email": "noone@example.com"})
    assert no_ws.status_code == 403


def test_members_and_removal_require_access(client, exchange, admin_headers):
    alice = exchange("alice@example.com")
    ws = client.post("/api/workspaces", headers=alice, json={"name": "Secret workspace"}).json()
    stranger = exchange("stranger@example.com")

    assert (
        client.get(f"/api/users/workspaces/{ws['id']}/members", headers=stranger).status_code == 403
    )
    assert (
        client.delete(f"/api/users/workspaces/{ws['id']}/members/someone", headers=stranger).status_code
        == 403
    )

    # Owner and admin can still read members; admin can list all users
    assert client.get(f"/api/users/workspaces/{ws['id']}/members", headers=alice).status_code == 200
    assert (
        client.get(f"/api/users/workspaces/{ws['id']}/members", headers=admin_headers).status_code == 200
    )
    assert client.get("/api/users/list", headers=admin_headers).status_code == 200


def test_workspace_member_removal_by_owner(client, auth_headers):
    ws = client.post("/api/workspaces", headers=auth_headers, json={"name": "Team"}).json()
    invite = client.post(
        "/api/users/invite",
        headers=auth_headers,
        json={"email": "dave@example.com", "workspace_id": ws["id"]},
    )
    assert invite.status_code == 201

    members = client.get(f"/api/users/workspaces/{ws['id']}/members", headers=auth_headers).json()["members"]
    dave = next(m for m in members if m["email"] == "dave@example.com")
    resp = client.delete(
        f"/api/users/workspaces/{ws['id']}/members/{dave['user_id']}", headers=auth_headers
    )
    assert resp.status_code == 200

    remaining = client.get(f"/api/users/workspaces/{ws['id']}/members", headers=auth_headers).json()["members"]
    assert all(m["email"] != "dave@example.com" for m in remaining)


def test_invite_creates_no_predictable_password(client, admin_headers):
    resp = client.post("/api/users/invite", headers=admin_headers, json={"email": "no-pw@example.com"})
    assert resp.status_code == 201

    with client.app.state.SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "no-pw@example.com"))
        assert user is not None
        assert user.password_hash  # random password hash, never a known default

    # The old predictable default no longer authenticates
    login = client.post(
        "/api/auth/login", json={"email": "no-pw@example.com", "password": "SalarUser123!"}
    )
    assert login.status_code == 401