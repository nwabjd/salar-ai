# tests/test_ollama.py
"""Tests for the local-mode (Ollama) API helpers, incl. Consensus Dual-Brain passthrough."""
from app.api.ollama import build_ollama_chat_payload

TOOLS = [{"type": "function", "function": {"name": "list_files"}}]


def test_payload_plain():
    p = build_ollama_chat_payload("salar-gemma4-e2b", [{"role": "user", "content": "hi"}], TOOLS)
    assert p == {"model": "salar-gemma4-e2b", "messages": [{"role": "user", "content": "hi"}], "tools": TOOLS}


def test_payload_with_consensus_model():
    p = build_ollama_chat_payload("salar-gemma4-e2b", [{"role": "user", "content": "hi"}], TOOLS, "salar-gemma4-e4b")
    assert p["consensus_model"] == "salar-gemma4-e4b"


def test_payload_ignores_same_or_empty_consensus():
    p_same = build_ollama_chat_payload("m", [{"role": "user", "content": "hi"}], TOOLS, "m")
    assert "consensus_model" not in p_same
    p_empty = build_ollama_chat_payload("m", [{"role": "user", "content": "hi"}], TOOLS, "")
    assert "consensus_model" not in p_empty
    p_none = build_ollama_chat_payload("m", [{"role": "user", "content": "hi"}], TOOLS, None)
    assert "consensus_model" not in p_none