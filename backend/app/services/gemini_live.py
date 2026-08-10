from typing import Dict, List
from urllib.parse import quote_plus


GEMINI_LIVE_ENDPOINT = (
    "wss://generativelanguage.googleapis.com/ws/"
    "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
)

SYSTEM_PROMPT = (
    "You are SALAR, a warm, concise personal AI companion in a live voice conversation. "
    "Speak naturally. Usually answer in one to three sentences unless the user asks for detail. "
    "Never claim an action completed unless it actually completed. Never talk over the user."
)


def gemini_live_url(api_key: str) -> str:
    return f"{GEMINI_LIVE_ENDPOINT}?key={quote_plus(api_key)}"


def build_setup(model: str, voice: str = "Kore", handle: str = "") -> Dict:
    setup = {
        "model": f"models/{model}",
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "inputAudioTranscription": {},
        "outputAudioTranscription": {},
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}
            },
            "thinkingConfig": {"thinkingLevel": "minimal"},
        },
        "realtimeInputConfig": {
            "automaticActivityDetection": {
                "disabled": False,
                "startOfSpeechSensitivity": "START_SENSITIVITY_HIGH",
                "endOfSpeechSensitivity": "END_SENSITIVITY_HIGH",
                "prefixPaddingMs": 20,
                "silenceDurationMs": 300,
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
    content = message.get("serverContent") or {}
    for part in (content.get("modelTurn") or {}).get("parts") or []:
        inline = part.get("inlineData") or {}
        if inline.get("data"):
            events.append({"type": "audio", "data": inline["data"]})
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
