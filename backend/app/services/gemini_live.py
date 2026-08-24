from typing import Dict, List
from urllib.parse import quote_plus


GEMINI_LIVE_ENDPOINT = (
    "wss://generativelanguage.googleapis.com/ws/"
    "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
)

SYSTEM_PROMPT = (
    "You are SALAR, a warm, concise personal AI companion in a live voice conversation. "
    "Speak naturally. Usually answer in one to three sentences unless the user asks for detail. "
    "Never claim an action completed unless it actually completed. Never talk over the user. "
    "You can run commands, open apps/URLs, create/read/write files, and list directories on the user's computer. "
    "Paths are relative to the user's home folder. Default to creating files and folders on the Desktop. "
    "To create files inside a new folder, use write_file with the full path (e.g. 'Desktop/My Project/index.html') — "
    "it auto-creates parent directories. Do NOT use mkdir then move. "
    "When the user asks you to do something on their computer, execute the appropriate tool call immediately."
)

# Tools exposed to Gemini Live so it can control the user's PC.
_LIVE_TOOLS = [
    {
        "function_declarations": [
            {
                "name": "run_command",
                "description": "Run a shell command on the user's PC. Relative paths resolve against home (e.g. 'Desktop/test'). Example: start https://facebook.com",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Shell command to run"}
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "open_url",
                "description": "Open a website URL in the default web browser on the user's PC. Example: 'https://facebook.com'.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL or domain to open"}
                    },
                    "required": ["url"]
                }
            },
            {
                "name": "open_app",
                "description": "Open an application or program on the user's PC (e.g. 'chrome', 'notepad', 'spotify', 'calc').",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "app_name": {"type": "string", "description": "Name or executable of the application"}
                    },
                    "required": ["app_name"]
                }
            },
            {
                "name": "list_files",
                "description": "List files and directories at a given path on the user's PC.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path to list"}
                    }
                }
            },
            {
                "name": "read_file",
                "description": "Read the contents of a text file on the user's PC.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path to read"}
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "write_file",
                "description": "Write content to a file on the user's PC. Auto-creates parent folders. Use full path like 'Desktop/My Project/index.html' to create files inside new folders.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path to write"},
                        "content": {"type": "string", "description": "Content to write"}
                    },
                    "required": ["path", "content"]
                }
            },
            {
                "name": "get_system_info",
                "description": "Get system telemetry and paths from the user's PC.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "list_devices",
                "description": "List registered and connected devices for the user.",
                "parameters": {"type": "object", "properties": {}}
            }
        ]
    }
]


def gemini_live_url(api_key: str) -> str:
    return f"{GEMINI_LIVE_ENDPOINT}?key={quote_plus(api_key)}"


def build_setup(model: str, voice: str = "Kore", handle: str = "") -> Dict:
    setup = {
        "model": f"models/{model}",
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "tools": _LIVE_TOOLS,
        "inputAudioTranscription": {},
        "outputAudioTranscription": {},
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}
            },
        },
        "realtimeInputConfig": {
            "automaticActivityDetection": {
                "disabled": False,
                "startOfSpeechSensitivity": "START_SENSITIVITY_LOW",
                "endOfSpeechSensitivity": "END_SENSITIVITY_LOW",
                "prefixPaddingMs": 100,
                "silenceDurationMs": 700,
            }
        },
        "contextWindowCompression": {"slidingWindow": {}},
        "sessionResumption": {**({"handle": handle} if handle else {})},
    }
    return {"setup": setup}


def build_audio_input(data: str) -> Dict:
    return {
        "realtimeInput": {
            "audio": {"data": data, "mimeType": "audio/pcm;rate=16000"}
        }
    }


def build_text_input(text: str) -> Dict:
    return {"realtimeInput": {"text": text.strip()}}


def translate_server_message(message: Dict) -> List[Dict]:
    events: List[Dict] = []
    # 1. Top-level toolCall from Gemini Multimodal Live API
    tool_call = message.get("toolCall") or {}
    for fc in tool_call.get("functionCalls") or []:
        events.append({
            "type": "function_call",
            "name": fc.get("name", ""),
            "args": fc.get("args", {}),
            "id": fc.get("id", ""),
        })
    # 2. Server content
    content = message.get("serverContent") or {}
    for part in (content.get("modelTurn") or {}).get("parts") or []:
        inline = part.get("inlineData") or {}
        if inline.get("data"):
            events.append({"type": "audio", "data": inline["data"]})
        fc = part.get("functionCall")
        if fc:
            events.append({
                "type": "function_call",
                "name": fc.get("name", ""),
                "args": fc.get("args", {}),
                "id": fc.get("id", ""),
            })
    if (content.get("inputTranscription") or {}).get("text"):
        events.append({
            "type": "input_transcript_delta",
            "text": content["inputTranscription"]["text"],
        })
    if (content.get("outputTranscription") or {}).get("text"):
        events.append({
            "type": "output_transcript_delta",
            "text": content["outputTranscription"]["text"],
        })
    if content.get("interrupted"):
        events.append({"type": "interrupted"})
    if content.get("generationComplete") or content.get("turnComplete"):
        events.append({"type": "response_done"})
    resume = message.get("sessionResumptionUpdate") or {}
    if resume.get("resumable") and resume.get("newHandle"):
        events.append({"type": "resumption", "handle": resume["newHandle"]})
    if message.get("goAway") is not None:
        events.append({
            "type": "go_away",
            "time_left": (message["goAway"] or {}).get("timeLeft", ""),
        })
    return events


def classify_gemini_error(status: int, code: str) -> str:
    if status in {429, 500, 502, 503, 504} or code in {
        "RESOURCE_EXHAUSTED",
        "UNAVAILABLE",
        "ABORTED",
    }:
        return "retryable"
    return "configuration"
