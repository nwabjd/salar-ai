import asyncio
import json
import logging
from contextlib import suppress
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from ..models import User
from ..security import decode_backend_token

log = logging.getLogger(__name__)
router = APIRouter()

OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime"
ALLOWED_VOICES = {"marin", "cedar"}

SYSTEM_PROMPT = """You are SALAR, a warm, concise personal AI companion in a live voice conversation.
Speak naturally and respond with audio. Usually answer in one to three sentences unless the user asks for detail.
Do not claim an action was completed unless it actually was. If tools are unavailable, say so plainly.
Keep the conversation flowing, but never interrupt the user."""


def _build_session_update(model: str, voice: str = "marin") -> dict:
    selected_voice = voice if voice in ALLOWED_VOICES else "marin"
    return {
        "type": "session.update",
        "session": {
            "type": "realtime",
            "model": model,
            "instructions": SYSTEM_PROMPT,
            "output_modalities": ["audio"],
            "audio": {
                "input": {
                    "format": {"type": "audio/pcm", "rate": 24000},
                    "noise_reduction": {"type": "far_field"},
                    "transcription": {"model": "gpt-4o-mini-transcribe"},
                    "turn_detection": {
                        "type": "semantic_vad",
                        "eagerness": "low",
                        "create_response": True,
                        "interrupt_response": True,
                    },
                },
                "output": {
                    "format": {"type": "audio/pcm", "rate": 24000},
                    "voice": selected_voice,
                },
            },
            "max_output_tokens": 1024,
        },
    }


def _translate_openai_event(message: dict) -> Optional[dict]:
    event_type = message.get("type")
    translations = {
        "session.updated": {"type": "ready"},
        "input_audio_buffer.speech_started": {"type": "speech_started"},
        "input_audio_buffer.speech_stopped": {"type": "speech_stopped"},
        "response.done": {"type": "response_done"},
    }
    if event_type in translations:
        return translations[event_type]
    if event_type in {"response.output_audio.delta", "response.audio.delta"}:
        return {"type": "audio", "data": message.get("delta", "")}
    if event_type in {"response.output_audio_transcript.delta", "response.audio_transcript.delta"}:
        return {"type": "output_transcript_delta", "text": message.get("delta", "")}
    if event_type in {"response.output_audio_transcript.done", "response.audio_transcript.done"}:
        return {"type": "output_transcript_completed", "text": message.get("transcript", "")}
    if event_type == "conversation.item.input_audio_transcription.delta":
        return {"type": "input_transcript_delta", "text": message.get("delta", "")}
    if event_type == "conversation.item.input_audio_transcription.completed":
        return {"type": "input_transcript_completed", "text": message.get("transcript", "")}
    if event_type == "error":
        error = message.get("error") or {}
        return {"type": "error", "error": "Realtime service error", "code": error.get("code", "upstream_error")}
    return None


def _authenticated_user(websocket: WebSocket, token: str) -> Optional[User]:
    payload = decode_backend_token(token, websocket.app.state.settings.jwt_secret)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    with websocket.app.state.SessionLocal() as db:
        return db.scalar(select(User).where(User.id == user_id))


async def _proxy_openai(client_ws: WebSocket, upstream, model: str, voice: str) -> None:
    await upstream.send(json.dumps(_build_session_update(model, voice)))

    async def forward_to_openai() -> None:
        while True:
            message = json.loads(await client_ws.receive_text())
            message_type = message.get("type")
            if message_type == "audio" and isinstance(message.get("data"), str):
                await upstream.send(json.dumps({"type": "input_audio_buffer.append", "audio": message["data"]}))
            elif message_type == "text" and isinstance(message.get("text"), str) and message["text"].strip():
                await upstream.send(json.dumps({
                    "type": "conversation.item.create",
                    "item": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": message["text"].strip()}]},
                }))
                await upstream.send(json.dumps({"type": "response.create"}))
            elif message_type == "cancel_response":
                await upstream.send(json.dumps({"type": "response.cancel"}))

    async def forward_to_client() -> None:
        async for raw in upstream:
            translated = _translate_openai_event(json.loads(raw))
            if translated:
                await client_ws.send_json(translated)

    tasks = [asyncio.create_task(forward_to_openai()), asyncio.create_task(forward_to_client())]
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    for task in done:
        with suppress(WebSocketDisconnect, asyncio.CancelledError):
            task.result()


@router.websocket("/ws/live")
async def live_ws(websocket: WebSocket):
    await websocket.accept()
    settings = websocket.app.state.settings

    try:
        setup = json.loads(await asyncio.wait_for(websocket.receive_text(), timeout=10))
        if setup.get("type") != "setup" or not isinstance(setup.get("token"), str):
            raise HTTPException(status_code=401, detail="Authentication required")
        user = _authenticated_user(websocket, setup["token"])
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
    except (HTTPException, ValueError, asyncio.TimeoutError):
        await websocket.send_json({"type": "error", "error": "Authentication required", "code": "unauthorized"})
        await websocket.close(code=1008)
        return

    if not settings.openai_api_key:
        await websocket.send_json({"type": "error", "error": "Live voice is not configured", "code": "not_configured"})
        await websocket.close(code=1011)
        return

    voice = setup.get("voice", "marin")
    try:
        import websockets

        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "OpenAI-Beta": "realtime=v1",
        }
        async with websockets.connect(OPENAI_REALTIME_URL, extra_headers=headers, max_size=2**22) as upstream:
            await _proxy_openai(websocket, upstream, settings.openai_realtime_model, voice)
    except WebSocketDisconnect:
        log.info("Live client disconnected")
    except Exception:
        log.exception("OpenAI Realtime connection failed")
        with suppress(Exception):
            await websocket.send_json({"type": "error", "error": "Live voice connection failed", "code": "upstream_unavailable"})
    finally:
        with suppress(Exception):
            await websocket.close()
