import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from ..security import get_current_user
from ..services.ollama import list_ollama_models, ollama_chat, ollama_is_available

log = logging.getLogger(__name__)
router = APIRouter(tags=["ollama"])


@router.get("/ollama/models")
async def get_models(request: Request, user=Depends(get_current_user)):
    """List available Ollama models."""
    base_url = request.app.state.settings.ollama_base_url
    models = await list_ollama_models(base_url)
    available = await ollama_is_available(base_url)
    return {"available": available, "models": models, "default": request.app.state.settings.ollama_default_model}


@router.post("/ollama/chat")
async def chat(request: Request, user=Depends(get_current_user)):
    """Stream chat from local Ollama with SALAR personality."""
    body = await request.json()
    messages = body.get("messages", [])
    model = body.get("model", request.app.state.settings.ollama_default_model)
    base_url = request.app.state.settings.ollama_base_url

    if not messages:
        return {"error": "No messages provided"}

    async def stream():
        try:
            async for chunk in ollama_chat(messages, model=model, base_url=base_url):
                yield f"data: {json.dumps({'type': 'text', 'text': chunk})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as exc:
            log.warning("Ollama chat error: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'error': str(exc)})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/ollama/status")
async def status(request: Request, user=Depends(get_current_user)):
    """Check Ollama connection status."""
    base_url = request.app.state.settings.ollama_base_url
    available = await ollama_is_available(base_url)
    return {"available": available, "url": base_url}
