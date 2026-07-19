def test_conversation_and_chat_are_persisted(client, auth_headers):
    created = client.post("/api/conversations", json={"title": "Foundation"}, headers=auth_headers)
    assert created.status_code == 201
    conversation_id = created.json()["id"]

    reply = client.post(
        "/api/chat",
        json={"conversation_id": conversation_id, "content": "What are we building?"},
        headers=auth_headers,
    )
    assert reply.status_code == 200
    assert reply.json()["assistant_message"]["content"] == "Test response to: What are we building?"

    detail = client.get(f"/api/conversations/{conversation_id}", headers=auth_headers)
    assert [message["role"] for message in detail.json()["messages"]] == ["user", "assistant"]


def test_user_cannot_access_another_users_conversation(client, auth_headers):
    response = client.get("/api/conversations/not-owned", headers=auth_headers)
    assert response.status_code == 404

