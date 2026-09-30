import asyncio
import base64
import json
import logging
import random
import struct
from typing import AsyncIterator, Dict, List

import httpx

log = logging.getLogger(__name__)


class GeminiBusyError(RuntimeError):
    """Gemini is overloaded / rate-limited (HTTP 429/503) after all retries."""

    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.status = status


class GeminiClient:
    """Google Gemini cloud LLM client using direct REST API via httpx."""

    BASE = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, api_key: str, model: str = "gemini-3.1-flash-lite"):
        if not api_key:
            raise ValueError("Gemini API key is required")
        self.api_key = api_key
        self.model = model
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(connect=10, read=90, write=10, pool=10))

    async def close(self):
        await self._client.aclose()

    def _contents(self, messages: List[Dict[str, str]]):
        system_instruction = None
        contents = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_instruction = content
                continue
            gemini_role = "model" if role == "assistant" else "user"
            if isinstance(content, list) and content and isinstance(content[0], dict) and ("functionCall" in content[0] or "functionResponse" in content[0]):
                contents.append({"role": gemini_role, "parts": content})
            else:
                contents.append({"role": gemini_role, "parts": [{"text": content}]})
        return contents, system_instruction

    def _body(self, messages: List[Dict[str, str]], tools: list = None) -> dict:
        contents, system_instruction = self._contents(messages)
        body: dict = {"contents": contents}
        if system_instruction:
            body["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        if tools:
            body["tools"] = tools
        return body

    async def chat_with_tools(self, messages: List[Dict[str, str]], tools: list) -> dict:
        body = self._body(messages, tools)
        data = await self._request_with_retry(
            f"{self.BASE}/models/{self.model}:generateContent", body
        )
        candidate = data.get("candidates", [{}])[0]
        parts = candidate.get("content", {}).get("parts", [])
        text_parts = [p.get("text", "") for p in parts if "text" in p]
        function_parts = [p.get("functionCall", {}) for p in parts if "functionCall" in p]
        return {
            "text": "".join(text_parts).strip(),
            "function_calls": function_parts,
            "finish_reason": candidate.get("finishReason", ""),
        }

    async def _request_with_retry(self, url: str, body: dict, retries: int = 6) -> dict:
        last_status = None
        last_detail = ""
        for attempt in range(retries):
            try:
                r = await self._client.post(url, params={"key": self.api_key}, json=body)
                if r.status_code == 200:
                    return r.json()
                if r.status_code in (429, 503):
                    last_status, last_detail = r.status_code, r.text[:200]
                    retry_after = r.headers.get("retry-after")
                    try:
                        wait = min(int(retry_after), 30)
                    except (TypeError, ValueError):
                        wait = min(2 ** attempt + random.uniform(0.5, 1.5), 25)
                    log.warning(
                        "Gemini %d (attempt %d/%d), retrying in %.1fs...",
                        r.status_code, attempt + 1, retries, wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                log.error("Gemini HTTP %d: %s", r.status_code, r.text[:200])
                r.raise_for_status()
            except httpx.TimeoutException as e:
                last_status = last_status or 0
                last_detail = f"timeout: {e}"
                log.warning("Gemini timeout (attempt %d/%d): %s", attempt + 1, retries, e)
                await asyncio.sleep(min(2 ** attempt + random.uniform(0.5, 1.5), 15))
            except httpx.HTTPStatusError:
                raise
            except Exception as e:
                last_status = last_status or 0
                last_detail = str(e)[:200]
                log.warning("Gemini connection error (attempt %d/%d): %s", attempt + 1, retries, e)
                await asyncio.sleep(min(2 ** attempt + random.uniform(0.5, 1.5), 15))
        raise GeminiBusyError(
            f"Gemini unavailable after {retries} attempts (last HTTP {last_status}: {last_detail[:150]})",
            status=last_status or 0,
        )

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        body = self._body(messages)
        data = await self._request_with_retry(
            f"{self.BASE}/models/{self.model}:generateContent", body
        )
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError) as e:
            log.error("Unexpected Gemini response structure: %s", json.dumps(data)[:500])
            raise RuntimeError(f"Gemini returned unexpected response: {e}") from e

    async def chat_with_image(self, prompt: str, image_bytes: bytes, mime_type: str = "image/png") -> str:
        import base64
        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode()}},
                    ],
                }
            ]
        }
        data = await self._request_with_retry(
            f"{self.BASE}/models/{self.model}:generateContent", body
        )
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Gemini vision returned unexpected response: {e}") from e

    async def chat_stream(self, messages: List[Dict[str, str]]) -> AsyncIterator[str]:
        body = self._body(messages)
        url = f"{self.BASE}/models/{self.model}:streamGenerateContent"
        for attempt in range(3):
            try:
                async with self._client.stream(
                    "POST", url, params={"key": self.api_key, "alt": "sse"}, json=body,
                ) as response:
                    if response.status_code in (429, 503):
                        wait = min(2 ** attempt + 1, 15)
                        log.warning("Gemini stream %d, retrying in %ds...", response.status_code, wait)
                        await asyncio.sleep(wait)
                        continue
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        try:
                            chunk = json.loads(line[6:])
                            token = chunk["candidates"][0]["content"]["parts"][0].get("text", "")
                            if token:
                                yield token
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
                    return
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (429, 503) and attempt < 2:
                    wait = min(2 ** attempt + 1, 15)
                    log.warning("Gemini stream error %d, retrying in %ds...", e.response.status_code, wait)
                    await asyncio.sleep(wait)
                    continue
                raise
            except httpx.TimeoutException as e:
                if attempt < 2:
                    log.warning("Gemini stream timeout (attempt %d), retrying...", attempt + 1)
                    await asyncio.sleep(min(2 ** attempt, 8))
                    continue
                raise

    async def stt(self, audio_bytes: bytes, mime_type: str = "audio/webm") -> str:
        audio_b64 = base64.b64encode(audio_bytes).decode()
        body = {
            "contents": [{
                "parts": [
                    {"text": "Transcribe this audio exactly as spoken. Output only the transcription, nothing else."},
                    {"inlineData": {"mimeType": mime_type, "data": audio_b64}},
                ]
            }],
        }
        data = await self._request_with_retry(
            f"{self.BASE}/models/{self.model}:generateContent", body
        )
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError):
            raise RuntimeError("Gemini STT returned unexpected response")

    async def tts(self, text: str) -> bytes:
        body = {
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {"voiceName": "Kore"}
                    }
                },
            },
        }
        tts_model = "gemini-2.5-flash-preview-tts"
        data = await self._request_with_retry(
            f"{self.BASE}/models/{tts_model}:generateContent", body
        )
        try:
            audio_b64 = data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
        except (KeyError, IndexError):
            raise RuntimeError("Gemini TTS returned unexpected response")
        pcm_data = base64.b64decode(audio_b64)
        return self._pcm_to_wav(pcm_data, sample_rate=24000, channels=1, sample_width=2)

    @staticmethod
    def _pcm_to_wav(pcm_data: bytes, sample_rate: int = 24000, channels: int = 1, sample_width: int = 2) -> bytes:
        data_size = len(pcm_data)
        header = struct.pack(
            '<4sI4s4sIHHIIHH4sI',
            b'RIFF', 36 + data_size, b'WAVE',
            b'fmt ', 16, 1, channels, sample_rate,
            sample_rate * channels * sample_width, channels * sample_width, sample_width * 8,
            b'data', data_size,
        )
        return header + pcm_data
