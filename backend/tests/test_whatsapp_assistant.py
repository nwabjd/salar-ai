from app.api.whatsapp import build_auto_reply_messages, normalize_auto_reply


def test_whatsapp_prompt_identifies_jds_assistant_and_handles_queries_professionally():
    messages = build_auto_reply_messages("Aisha", "Hello, can you help me?", False)
    prompt = messages[0]["content"]

    assert "JD's assistant" in prompt
    assert "ask a focused follow-up" in prompt
    assert "Do not fabricate" in prompt
    assert "I will not" in prompt
    assert messages[1]["content"] == "WhatsApp DM message from Aisha: Hello, can you help me?"


def test_whatsapp_reply_normalization_preserves_pass_message_audit_signal():
    reply, pass_message = normalize_auto_reply("GOTOPASS: Please ask JD to call me tomorrow.")
    assert reply == "Thank you. I’ll make sure JD receives your message. Is there anything else I can help you with?"
    assert pass_message == "Please ask JD to call me tomorrow."


def test_whatsapp_reply_has_a_professional_fallback():
    reply, pass_message = normalize_auto_reply("")
    assert reply == "Hello, this is JD’s assistant. How may I help you today?"
    assert pass_message is None
