import asyncio
import json
import logging
import base64

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

log = logging.getLogger(__name__)
router = APIRouter()

GEMINI_WS_URL = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
LIVE_MODEL = "models/gemini-3.1-flash-live-preview"


def _build_setup_message(api_key: str, system_instruction: str) -> dict:
    return {
        "setup": {
            "model": LIVE_MODEL,
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": "Kore"
                        }
                    }
                }
            },
            "systemInstruction": {
                "parts": [{"text": system_instruction}]
            },
            "tools": []
        }
    }


SYSTEM_PROMPT = """You are SALAR, a personal AI assistant running as a voice assistant. 
You are helpful, concise, and friendly. 
Speak naturally and conversationally. 
Keep responses brief — 1-3 sentences unless the user asks for detail.
You can control the user's computer, manage files, send messages, search the web, and much more through your connected tools.
When the user asks you to do something on their computer, acknowledge and describe what you're doing.
Be warm and personable. Use the user's name when you know it."""


async def _proxy_gemini(client_ws: WebSocket, gemini_ws_url: str, api_key: str):
    """Open a WebSocket to Gemini Live API and bidirectionally proxy messages."""
    import websockets

    full_url = f"{gemini_ws_url}?key={api_key}"
    log.info("Connecting to Gemini Live API...")

    try:
        async with websockets.connect(full_url, max_size=2**22) as gemini_ws:
            log.info("Connected to Gemini Live API")

            setup_msg = _build_setup_message(api_key, SYSTEM_PROMPT)
            await gemini_ws.send(json.dumps(setup_msg))
            log.info("Sent setup message to Gemini")

            async def forward_to_gemini():
                try:
                    while True:
                        data = await client_ws.receive_text()
                        msg = json.loads(data)

                        if msg.get("type") == "setup":
                            setup_msg["setup"]["generationConfig"]["responseModalities"] = msg.get("modalities", ["AUDIO"])
                            if msg.get("voice"):
                                setup_msg["setup"]["generationConfig"]["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] = msg["voice"]
                            await gemini_ws.send(json.dumps(setup_msg))
                            log.info("Updated setup: voice=%s", msg.get("voice", "Kore"))
                        elif msg.get("type") == "audio":
                            await gemini_ws.send(json.dumps({
                                "realtimeInput": {
                                    "mediaChunks": [{
                                        "mimeType": "audio/pcm;rate=16000",
                                        "data": msg["data"]
                                    }]
                                }
                            }))
                        elif msg.get("type") == "end":
                            await gemini_ws.send(json.dumps({"clientBreak": {}}))
                        else:
                            await gemini_ws.send(json.dumps(msg))
                except WebSocketDisconnect:
                    log.info("Client disconnected during forward")
                except Exception as e:
                    log.error("Forward to Gemini error: %s", e)

            async def forward_to_client():
                try:
                    async for raw in gemini_ws:
                        msg = json.loads(raw)
                        if "serverContent" in msg:
                            sc = msg["serverContent"]
                            model_turn = sc.get("modelTurn", {})
                            parts = model_turn.get("parts", [])
                            for part in parts:
                                if "inlineData" in part:
                                    await client_ws.send_json({
                                        "type": "audio",
                                        "data": part["inlineData"]["data"],
                                        "mimeType": part["inlineData"].get("mimeType", "audio/pcm;rate=24000")
                                    })
                                elif "text" in part:
                                    await client_ws.send_json({
                                        "type": "text",
                                        "text": part["text"]
                                    })
                            if sc.get("turnComplete"):
                                await client_ws.send_json({"type": "turnComplete"})
                            if sc.get("interrupted"):
                                await client_ws.send_json({"type": "interrupted"})
                        elif "setupComplete" in msg:
                            log.info("Gemini setup complete")
                            await client_ws.send_json({"type": "ready"})
                        elif "toolCall" in msg:
                            log.info("Gemini tool call: %s", msg.get("toolCall", {}).get("name", "unknown"))
                            await client_ws.send_json({"type": "toolCall", "toolCall": msg["toolCall"]})
                        elif "toolCallCancellation" in msg:
                            await client_ws.send_json({"type": "toolCallCancellation", "toolCallCancellation": msg["toolCallCancellation"]})
                        else:
                            log.debug("Gemini message: %s", json.dumps(msg)[:200])
                except Exception as e:
                    log.error("Forward to client error: %s", e)

            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(forward_to_gemini()),
                    asyncio.create_task(forward_to_client()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
    except Exception as e:
        log.error("Gemini WebSocket connection failed: %s", e)
        try:
            await client_ws.send_json({"type": "error", "error": str(e)})
        except Exception:
            pass


@router.websocket("/ws/live")
async def live_ws(websocket: WebSocket):
    """WebSocket proxy between the browser and Gemini Live API."""
    await websocket.accept()

    from ..config import Settings
    settings = Settings()
    api_key = settings.gemini_api_key

    if not api_key:
        await websocket.send_json({"type": "error", "error": "No Gemini API key configured"})
        await websocket.close()
        return

    log.info("Live WebSocket client connected")
    await _proxy_gemini(websocket, GEMINI_WS_URL, api_key)
    log.info("Live WebSocket session ended")
