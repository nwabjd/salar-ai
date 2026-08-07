from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import Conversation, Message, User


def user_id_by_email(client, email):
    with client.app.state.SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        return user.id


def seed_messages(client, user_id, count, age_days=0):
    with client.app.state.SessionLocal() as db:
        conv = Conversation(user_id=user_id, title="quota")
        db.add(conv)
        db.flush()
        for i in range(count):
            db.add(
                Message(
                    conversation_id=conv.id,
                    role="user",
                    content=f"m{i}",
                    created_at=datetime.now(timezone.utc) - timedelta(days=age_days),
                )
            )
        db.commit()
        return conv.id


def create_conversation(client, headers):
    resp = client.post("/api/conversations", json={"title": "q"}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def test_free_user_under_limit_can_chat(client, exchange):
    headers = exchange("under@example.com")
    conv_id = create_conversation(client, headers)
    resp = client.post("/api/chat", json={"conversation_id": conv_id, "content": "hello"}, headers=headers)
    assert resp.status_code == 200


def test_free_user_at_limit_gets_429(client, exchange):
    client.app.state.settings.free_monthly_quota = 2
    headers = exchange("atlimit@example.com")
    user_id = user_id_by_email(client, "atlimit@example.com")
    seed_messages(client, user_id, 2)
    conv_id = create_conversation(client, headers)

    resp = client.post("/api/chat", json={"conversation_id": conv_id, "content": "hello"}, headers=headers)

    assert resp.status_code == 429
    detail = resp.json()["detail"]
    assert detail["quota_exceeded"] is True
    assert detail["limit"] == 2
    assert detail["used"] == 2
    assert detail["reset_at"]


def test_agent_endpoint_respects_quota(client, exchange):
    client.app.state.settings.free_monthly_quota = 1
    headers = exchange("agent@example.com")
    user_id = user_id_by_email(client, "agent@example.com")
    seed_messages(client, user_id, 1)
    conv_id = create_conversation(client, headers)

    resp = client.post("/api/agent", json={"conversation_id": conv_id, "content": "run"}, headers=headers)

    assert resp.status_code == 429
    assert resp.json()["detail"]["quota_exceeded"] is True


def test_pro_user_uses_pro_limit(client, exchange):
    client.app.state.settings.pro_monthly_quota = 3
    client.app.state.settings.free_monthly_quota = 500
    headers = exchange("pro@example.com")
    user_id = user_id_by_email(client, "pro@example.com")
    with client.app.state.SessionLocal() as db:
        user = db.get(User, user_id)
        user.plan = "pro"
        db.commit()
    seed_messages(client, user_id, 2)
    conv_id = create_conversation(client, headers)

    ok = client.post("/api/chat", json={"conversation_id": conv_id, "content": "a"}, headers=headers)
    assert ok.status_code == 200

    seed_messages(client, user_id, 1)
    blocked = client.post("/api/chat", json={"conversation_id": conv_id, "content": "b"}, headers=headers)
    assert blocked.status_code == 429
    assert blocked.json()["detail"]["limit"] == 3


def test_admin_exempt_from_quota(client, admin_headers):
    client.app.state.settings.free_monthly_quota = 1
    with client.app.state.SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "nwabjd@gmail.com"))
        seed_conv = Conversation(user_id=user.id, title="seed")
        db.add(seed_conv)
        db.flush()
        for i in range(5):
            db.add(Message(conversation_id=seed_conv.id, role="user", content=f"s{i}"))
        db.commit()
    conv_id = create_conversation(client, admin_headers)

    resp = client.post("/api/chat", json={"conversation_id": conv_id, "content": "admin"}, headers=admin_headers)
    assert resp.status_code == 200


def test_usage_only_counts_current_month(client, exchange):
    headers = exchange("stale@example.com")
    user_id = user_id_by_email(client, "stale@example.com")
    seed_messages(client, user_id, 3, age_days=40)

    usage = client.get("/api/billing/usage", headers=headers)
    assert usage.status_code == 200
    assert usage.json()["used"] == 0


def test_billing_usage_endpoint_shape(client, exchange):
    headers = exchange("shape@example.com")
    body = client.get("/api/billing/usage", headers=headers).json()
    assert {"plan", "limit", "used", "reset_at", "exempt"} <= set(body.keys())
    assert body["plan"] == "free"
    assert body["exempt"] is False
