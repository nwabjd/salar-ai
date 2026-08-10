import asyncio
import json
import logging
from contextlib import suppress
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from ..models import User
from ..security import decode_backend_token
from ..services.gemini_live import (
    build_audio_input,
    build_setup,
    build_text_input,
    classify_gemini_error,
    gemini_live_url,
    translate_server_message,
)

log = logging.getLogger(__name__)
router = APIRouter()

READY = {"type": "ready"}
RETRYING = {"type": "provider_retry", "error": "Live voice is reconnecting"}
FALLBACK = {"type": "fallback_required", "error": "Switching voice connection"}
NOT_CONFIGURED = {
    "type": "error",
    "error": "Live voice is not configured",
    "code": "not_configured",
}


class _GeminiReconnect(Exception):
    def __init__(self, handle: str = ""):
        super().__init__("Gemini Live reconnect requested")
        self.handle = handle


def _translate_provider_event(message: dict) -> list[dict]:
    if "setupComplete" in message:
        return [READY]
    error = message.get("error") or {}
    if error:
        try:
            status = int(error.get("code") or 0)
        except (TypeError, ValueError):
            status = 0
        code = str(error.get("status") or "UNKNOWN")
        if classify_gemini_error(status, code) == "retryable":
            return [RETRYING]
        return [{
            "type": "error",
            "error": "Live voice configuration failed",
            "code": "configuration",
        }]
    return translate_server_message(message)


def _authenticated_user(websocket: WebSocket, token: str) -> Optional[User]:
    payload = decode_backend_token(token, websocket.app.state.settings.jwt_secret)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    with websocket.app.state.SessionLocal() as db:
        return db.scalar(select(User).where(User.id == user_id))


async def _proxy_gemini(
    client_ws: WebSocket,
    upstream,
    model: str,
    resume_handle: str = "",
) -> str:
    await upstream.send(json.dumps(build_setup(model, "Kore", resume_handle)))
    latest_handle = resume_handle
    input_transcript = ""
    output_transcript = ""

    async def forward_to_gemini() -> None:
        while True:
            message = json.loads(await client_ws.receive_text())
            message_type = message.get("type")
            if message_type == "audio" and isinstance(message.get("data"), str):
                await upstream.send(json.dumps(build_audio_input(message["data"])))
            elif (
                message_type == "text"
                and isinstance(message.get("text"), str)
                and message["text"].strip()
            ):
                await upstream.send(json.dumps(build_text_input(message["text"])))

    async def forward_to_client() -> None:
        nonlocal latest_handle, input_transcript, output_transcript
        async for raw in upstream:
            source = json.loads(raw)
            for event in _translate_provider_event(source):
                event_type = event.get("type")
                if event_type == "resumption":
                    latest_handle = event.get("handle", "")
                    continue
                if event_type == "go_away":
                    raise _GeminiReconnect(latest_handle)
                if event_type == "provider_retry":
                    error = source.get("error") or {}
                    log.warning(
                        "Gemini Live retryable error status=%s code=%s",
                        error.get("code", "unknown"),
                        error.get("status", "unknown"),
                    )
                    raise _GeminiReconnect(latest_handle)
                if event_type == "input_transcript_delta":
                    input_transcript += event.get("text", "")
                elif event_type == "output_transcript_delta":
                    output_transcript += event.get("text", "")
                elif event_type == "interrupted":
                    output_transcript = ""
                elif event_type == "response_done":
                    if input_transcript.strip():
                        await client_ws.send_json({
                            "type": "input_transcript_completed",
                            "text": input_transcript.strip(),
                        })
                        input_transcript = ""
                    if output_transcript.strip():
                        await client_ws.send_json({
                            "type": "output_transcript_completed",
                            "text": output_transcript.strip(),
                        })
                        output_transcript = ""
                await client_ws.send_json(event)
        raise _GeminiReconnect(latest_handle)

    tasks = [
        asyncio.create_task(forward_to_gemini()),
        asyncio.create_task(forward_to_client()),
    ]
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    for task in done:
        task.result()
    return latest_handle


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
        await websocket.send_json({
            "type": "error",
            "error": "Authentication required",
            "code": "unauthorized",
        })
        await websocket.close(code=1008)
        return

    if not settings.gemini_api_key:
        await websocket.send_json(NOT_CONFIGURED)
        await websocket.close(code=1011)
        return

    resume_handle = ""
    try:
        import websockets

        for attempt in range(2):
            try:
                url = gemini_live_url(settings.gemini_api_key)
                async with websockets.connect(url, max_size=2**22) as upstream:
                    resume_handle = await _proxy_gemini(
                        websocket,
                        upstream,
                        settings.gemini_live_model,
                        resume_handle,
                    )
                return
            except _GeminiReconnect as exc:
                resume_handle = exc.handle or resume_handle
                if attempt == 0:
                    await websocket.send_json(RETRYING)
                    continue
                await websocket.send_json(FALLBACK)
                return
            except WebSocketDisconnect:
                return
            except Exception as exc:
                log.warning("Gemini Live connection attempt %d failed: %s", attempt + 1, type(exc).__name__)
                if attempt == 0:
                    await websocket.send_json(RETRYING)
                    continue
                await websocket.send_json(FALLBACK)
                return
    finally:
        with suppress(Exception):
            await websocket.close()
