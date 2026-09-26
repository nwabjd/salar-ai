import json
import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import get_current_user
from ..services.agent import _route_to_local_device
from ..services.ollama import list_ollama_models, ollama_is_available

log = logging.getLogger(__name__)
router = APIRouter(tags=["ollama"])

# Compact PC-control toolset passed to the local Ollama model. The desktop app
# executes whatever the model calls via its existing local handlers.
_OLLAMA_TOOLS = [
    {"type": "function", "function": {
        "name": "run_command",
        "description": "Run a shell command on the user's PC (home directory). Prefer write_file for creating files.",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
    }},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "Write content to a file on the user's PC. Auto-creates parent folders. Full path like 'Desktop/MyProject/index.html'.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
    }},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read a text file on the user's PC.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "delete_file",
        "description": "Delete a file or folder from the user's PC. Relative paths resolve against home. Set recursive=true to delete a folder and its contents. Permanently deletes.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "recursive": {"type": "boolean"}}, "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "list_files",
        "description": "List all entries in a directory on the user's PC. Relative paths resolve against home; Desktop/Documents/Downloads/Pictures map to the user's real (OneDrive-aware) folders. Returns every entry (up to 2000; when truncated=true there are more, so drill into a subfolder).",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
    }},
    {"type": "function", "function": {
        "name": "open_url",
        "description": "Open a website in the user's default browser.",
        "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
    }},
    {"type": "function", "function": {
        "name": "open_app",
        "description": "Open an application on the user's PC (e.g. 'notepad', 'chrome').",
        "parameters": {"type": "object", "properties": {"app_name": {"type": "string"}}, "required": ["app_name"]},
    }},
    {"type": "function", "function": {
        "name": "set_volume",
        "description": "Set system volume 0-100 on the user's PC.",
        "parameters": {"type": "object", "properties": {"level": {"type": "integer", "minimum": 0, "maximum": 100}}, "required": ["level"]},
    }},
    {"type": "function", "function": {
        "name": "get_system_info",
        "description": "Get system info (OS, CPU, RAM, home/desktop paths) from the user's PC.",
        "parameters": {"type": "object", "properties": {}},
    }},
]


@router.get("/api/ollama/status")
async def status(request: Request, user=Depends(get_current_user)):
    """Check whether the user's connected desktop can reach a local Ollama server."""
    available = await ollama_is_available(request.app.state.settings.ollama_base_url)
    return {"available": available, "url": request.app.state.settings.ollama_base_url}


@router.get("/api/ollama/models")
async def get_models(request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """List models on the user's local Ollama. Ollama runs on the user's PC,
    so the list is fetched through their connected desktop app (same path as
    /api/ollama/chat); falls back to a server-side check when no device is
    registered."""
    default = request.app.state.settings.ollama_default_model
    routed = await _route_to_local_device("ollama_models", {}, user.id, db, wait_seconds=15)
    if routed and not routed.get("error"):
        models = routed.get("models") or []
        return {"available": bool(models), "models": models, "default": default}
    base_url = request.app.state.settings.ollama_base_url
    models = await list_ollama_models(base_url)
    available = await ollama_is_available(base_url)
    return {"available": available, "models": models, "default": default}


@router.post("/api/ollama/chat")
async def chat(
    request: Request,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Chat with the local fine-tuned SALAR model. Routed through the user's
    desktop app so Ollama (localhost:11434) and tool execution both happen on
    their own machine."""
    body = await request.json()
    messages = body.get("messages") or []
    if not messages:
        return {"error": "No messages provided"}
    model = body.get("model") or request.app.state.settings.ollama_default_model

    result = await _route_to_local_device(
        "ollama_chat",
        {"model": model, "messages": messages, "tools": _OLLAMA_TOOLS},
        user.id,
        db,
        wait_seconds=600,
    )
    if result is None:
        return {"error": "No connected device with Ollama. Open the SALAR desktop app and try again."}
    return result
