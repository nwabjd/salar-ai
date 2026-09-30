"""OpenAI-compatible chat client for SALAR's primary brain — with failover chain.

SALAR normally drives its LLM through the Gemini REST API. This client lets a
primary env-switchable OpenAI-compatible provider (Groq, OpenRouter, NVIDIA NIM,
…) power the same interface — ``chat`` and ``chat_with_tools`` — and automatically
fails over to alternate providers (e.g. NIM then Gemini) when the primary is
rate-limited or unavailable, so every message ends in an answer rather than
silence. The multimodal/audio methods (``chat_with_image``, ``stt``, ``tts``,
``chat_stream``) delegate to a Gemini fallback when provided.

Configured via SALAR_LLM_API_BASE_URL + SALAR_LLM_API_KEY + SALAR_LLM_API_MODEL
(OpenAI-compatible ``/chat/completions``). When those are set the coordinator is
built with this client instead of GeminiClient.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
from typing import AsyncIterator, Callable, Dict, List, Optional

import httpx

from .gemini import GeminiBusyError
from .nim import gemini_decl_to_openai_tools

log = logging.getLogger(__name__)


def _is_tool_use_error(response: httpx.Response) -> bool:
    """True when the provider rejects output that called a tool that wasn't offered."""
    if response.status_code != 400:
        return False
    text = (response.text or "").lower()
    return "tool_use_failed" in text or "tool choice is none" in text or "model called a tool" in text


class OpenAICompatClient:
    """Drop-in GeminiClient interface backed by OpenAI-compatible endpoints.

    ``alternates`` are objects exposing the same ``chat(messages)`` /
    ``chat_with_tools(messages, tools)`` duck-type interface (e.g. other
    OpenAICompatClient instances or a GeminiClient). They are tried in order when
    the primary raises a transient/busy error.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        vision: Optional[object] = None,
        alternates: Optional[List[object]] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        retries: int = 6,
    ):
        if not api_key or not base_url or not model:
            raise ValueError("OpenAI-compatible LLM requires api_key, base_url and model")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._vision = vision  # GeminiClient used for image/audio/stream fallbacks
        self._alternates = list(alternates or [])
        self._retries = retries
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(connect=10, read=90, write=10, pool=10),
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()
        for alt in self._alternates:
            closer = getattr(alt, "close", None)
            if closer is not None:
                try:
                    await closer()
                except Exception:  # noqa: BLE001
                    pass

    # ------------------------------------------------------------------ #
    # Message translation: Gemini-style list -> OpenAI-style list
    # ------------------------------------------------------------------ #
    def _translate_messages(self, messages: List[Dict]) -> List[Dict]:
        out: List[Dict] = []
        queues: Dict[str, List[str]] = {}

        def next_tool_id(name: str) -> str:
            ids = queues.setdefault(name, [])
            cid = f"call_{name}_{len(ids) + 1}"
            ids.append(cid)
            return cid

        for msg in messages or []:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            openai_role = "assistant" if role in ("model", "assistant") else role
            if role == "system":
                out.append({"role": "system", "content": content})
                continue
            if not (isinstance(content, list) and content and isinstance(content[0], dict)):
                out.append({"role": openai_role, "content": content})
                continue

            # Gemini structured parts (functionCall / functionResponse / text)
            text_parts: List[str] = []
            tool_calls: List[Dict] = []
            tool_msgs: List[Dict] = []
            for part in content:
                if "functionCall" in part:
                    fc = part["functionCall"]
                    name = fc.get("name", "")
                    args = fc.get("args") or {}
                    tool_calls.append({
                        "id": next_tool_id(name),
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(args)},
                    })
                elif "functionResponse" in part:
                    fr = part["functionResponse"]
                    name = fr.get("name", "")
                    cid = queues.get(name, [])
                    tool_id = cid.pop(0) if cid else f"call_{name}_1"
                    tool_msgs.append({
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "content": json.dumps(fr.get("response", {})),
                    })
                else:
                    text_parts.append(part.get("text", ""))
            if tool_calls:
                assistant_msg: Dict = {"role": "assistant", "tool_calls": tool_calls}
                text = "".join(text_parts).strip()
                if text:
                    assistant_msg["content"] = text
                out.append(assistant_msg)
            elif text_parts:
                out.append({"role": openai_role, "content": "\n".join(text_parts)})
            out.extend(tool_msgs)
        return out

    def _oai_tools(self, tools: list) -> List[Dict]:
        oai_tools: List[Dict] = []
        for group in tools or []:
            decls = group.get("function_declarations") or group.get("functionDeclarations") or []
            if decls:
                oai_tools.extend(gemini_decl_to_openai_tools(decls))
        return oai_tools

    # ------------------------------------------------------------------ #
    async def chat(self, messages: List[Dict[str, str]]) -> str:
        _NO_TOOLS_NOTE = (
            "No tools are available in this request. Do not call any tool — answer "
            "directly with what you know. If the user asked you to do something that "
            "would normally need a tool, say briefly that it can't be done here and "
            "suggest using the interactive chat."
        )

        async def _primary(messages=messages):
            body = {
                "model": self.model,
                "messages": self._translate_messages(messages),
                "max_tokens": 2048,
                "temperature": 0.7,
            }
            try:
                data = await self._request_with_retry("/chat/completions", body)
            except httpx.HTTPStatusError as e:
                if not _is_tool_use_error(e.response):
                    raise
                # gpt-oss-style models try to call tools even when the request
                # carries none; tell them tools are off and retry once, then hand
                # off to the failover chain if they still insist.
                body = {
                    **body,
                    "messages": [{"role": "system", "content": _NO_TOOLS_NOTE}, *body["messages"]],
                }
                try:
                    data = await self._request_with_retry("/chat/completions", body)
                except httpx.HTTPStatusError as e2:
                    if _is_tool_use_error(e2.response):
                        raise GeminiBusyError(
                            "LLM insists on tool use but this request has no tools", status=400
                        ) from e2
                    raise
            try:
                return (data["choices"][0]["message"].get("content") or "").strip()
            except (KeyError, IndexError, TypeError) as e:
                raise RuntimeError(f"LLM returned unexpected response: {e}") from e

        return await self._with_failover(_primary, "chat", messages)

    async def chat_with_tools(self, messages: List[Dict[str, str]], tools: list) -> dict:
        async def _primary(messages=messages, tools=tools):
            oai_tools = self._oai_tools(tools)
            body: Dict = {
                "model": self.model,
                "messages": self._translate_messages(messages),
                "max_tokens": 2048,
                "temperature": 0.7,
            }
            if oai_tools:
                body["tools"] = oai_tools
                body["tool_choice"] = "auto"
            data = await self._request_with_retry("/chat/completions", body)
            choice = (data.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            text = message.get("content") or ""
            function_calls = []
            for tc in message.get("tool_calls") or []:
                if tc.get("type") != "function":
                    continue
                fn = tc.get("function") or {}
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except (json.JSONDecodeError, TypeError):
                    args = {}
                function_calls.append({"name": fn.get("name", ""), "args": args})
            return {
                "text": text.strip() if isinstance(text, str) else "",
                "function_calls": function_calls,
                "finish_reason": choice.get("finish_reason") or "",
            }

        return await self._with_failover(_primary, "chat_with_tools", messages, tools)

    # ------------------------------------------------------------------ #
    # Failover: try the primary, then each alternate (busy/transient only).
    # ------------------------------------------------------------------ #
    async def _with_failover(
        self,
        try_primary: Callable,
        method_name: str,
        *args,
    ):
        try:
            return await try_primary()
        except GeminiBusyError as primary_err:
            last: Exception = primary_err
        except httpx.HTTPStatusError as primary_err:
            # 4xx (other than 429) usually means the request itself is bad —
            # every OpenAI-compatible alternate would fail the same way. Surface it.
            if 400 <= primary_err.response.status_code < 500 and primary_err.response.status_code != 429:
                raise
            last = primary_err
        except Exception as primary_err:  # noqa: BLE001 — connection/parse noise
            last = primary_err
        for alt in self._alternates:
            method = getattr(alt, method_name, None)
            if method is None:
                continue
            try:
                log.warning(
                    "LLM %s unavailable (%s) — failing over to %s",
                    self.model, type(last).__name__, getattr(alt, "model", "<alternate>"),
                )
                return await method(*args)
            except Exception as alt_err:  # noqa: BLE001
                last = alt_err
                log.warning("Failover provider %s failed: %s", getattr(alt, "model", "<alternate>"), alt_err)
        raise last

    # ------------------------------------------------------------------ #
    # Multimodal / audio methods delegate to the Gemini fallback
    # ------------------------------------------------------------------ #
    async def chat_with_image(self, prompt: str, image_bytes: bytes, mime_type: str = "image/png") -> str:
        if self._vision is not None:
            return await self._vision.chat_with_image(prompt, image_bytes, mime_type)
        raise RuntimeError("LLM provider does not support images and no vision fallback is configured")

    async def chat_stream(self, messages: List[Dict[str, str]]) -> AsyncIterator[str]:
        if self._vision is not None:
            async for token in self._vision.chat_stream(messages):
                yield token
            return
        raise RuntimeError("LLM provider does not support streaming and no fallback is configured")

    async def stt(self, audio_bytes: bytes, mime_type: str = "audio/webm") -> str:
        if self._vision is not None:
            return await self._vision.stt(audio_bytes, mime_type)
        raise RuntimeError("LLM provider does not support speech recognition and no fallback is configured")

    async def tts(self, text: str) -> bytes:
        if self._vision is not None:
            return await self._vision.tts(text)
        raise RuntimeError("LLM provider does not support speech synthesis and no fallback is configured")

    # ------------------------------------------------------------------ #
    async def _request_with_retry(self, url: str, body: dict, retries: Optional[int] = None) -> dict:
        retries = retries or self._retries
        last_status = None
        last_detail = ""
        for attempt in range(retries):
            try:
                r = await self._client.post(url, json=body)
                if r.status_code == 200:
                    return r.json()
                body_lower = (r.text or "").lower()
                # gpt-oss-style models occasionally emit unparseable tool-call
                # output (Groq HTTP 400 "Parsing failed") — retry like a rate limit.
                parse_failed = (
                    r.status_code == 400
                    and ("parsing failed" in body_lower or "could not be parsed" in body_lower)
                )
                if r.status_code in (429, 503) or parse_failed:
                    last_status, last_detail = r.status_code, r.text[:200]
                    retry_after = r.headers.get("retry-after")
                    try:
                        wait = min(int(retry_after), 30)
                    except (TypeError, ValueError):
                        wait = min(2 ** attempt + random.uniform(0.5, 1.5), 25)
                    log.warning(
                        "LLM %d (attempt %d/%d), retrying in %.1fs...",
                        r.status_code, attempt + 1, retries, wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                log.error("LLM HTTP %d: %s", r.status_code, r.text[:200])
                r.raise_for_status()
            except httpx.TimeoutException as e:
                last_status = last_status or 0
                last_detail = f"timeout: {e}"
                log.warning("LLM timeout (attempt %d/%d): %s", attempt + 1, retries, e)
                await asyncio.sleep(min(2 ** attempt + random.uniform(0.5, 1.5), 15))
            except httpx.HTTPStatusError:
                raise
            except Exception as e:
                last_status = last_status or 0
                last_detail = str(e)[:200]
                log.warning("LLM connection error (attempt %d/%d): %s", attempt + 1, retries, e)
                await asyncio.sleep(min(2 ** attempt + random.uniform(0.5, 1.5), 15))
        raise GeminiBusyError(
            f"LLM unavailable after {retries} attempts (last HTTP {last_status}: {last_detail[:150]})",
            status=last_status or 0,
        )