"""Official Meta WhatsApp Business Platform (Cloud API) adapter for the
WhatsApp Customer Service capability.

This is the ONLY place that talks to the Graph API for the customer-service
inbox. It never logs credentials. The existing per-user WhatsApp bridge
automation (services/whatsapp.py + backend/whatsapp/bridge.js) is untouched and
deliberately independent.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any, Dict, List, Optional

import httpx

log = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.facebook.com"


class WhatsAppCloudAPIError(Exception):
    """Raised for any failed Cloud API call.

    Attributes mirror the Meta error object so callers can decide on retries:
    ``retryable`` distinguishes transient failures (429, 5xx, network drop after
    send) from permanent ones (bad token, invalid template, undeliverable).
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        api_code: Optional[int] = None,
        retryable: bool = False,
        payload: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.api_code = api_code
        self.retryable = retryable
        self.payload = payload or {}

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"WhatsAppCloudAPIError(message={self.message!r}, status_code={self.status_code}, "
            f"api_code={self.api_code}, retryable={self.retryable})"
        )


class WhatsAppCloudClient:
    """Thin client for the WhatsApp Cloud API messages endpoint."""

    def __init__(
        self,
        access_token: Optional[str] = None,
        phone_number_id: Optional[str] = None,
        api_version: str = "v23.0",
        timeout: float = 30.0,
    ):
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.api_version = api_version
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10, read=timeout, write=15, pool=10)
        )

    async def close(self) -> None:
        try:
            await self._client.aclose()
        except Exception:  # pragma: no cover - defensive
            pass

    def _configured(self) -> bool:
        return bool(self.access_token and self.phone_number_id)

    def _message_url(self) -> str:
        return f"{GRAPH_BASE}/{self.api_version}/{self.phone_number_id}/messages"

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------ auth/signature

    @staticmethod
    def validate_signature(raw_body: bytes, signature_header: Optional[str], app_secret: str) -> bool:
        """Verify the X-Hub-Signature-256 header over the raw webhook body.

        Meta signs with HMAC-SHA256(key=app secret, msg=raw body) and sends
        ``sha256=<hex>``. Constant-time comparison prevents timing attacks.
        """
        if not signature_header or not app_secret:
            return False
        expected_prefix, _, provided = signature_header.partition("=")
        if expected_prefix.lower() != "sha256" or not provided:
            return False
        digest = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(digest, provided.lower())

    # ------------------------------------------------------------------ sending

    async def send_text(self, to: str, text: str, *, preview_url: bool = False) -> str:
        """Send a plain text message; returns the WhatsApp message id (wamid)."""
        if not text or not text.strip():
            raise WhatsAppCloudAPIError("text is required", retryable=False)
        body: Dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": preview_url, "body": text},
        }
        data = await self._post(self._message_url(), body)
        return self._first_message_id(data)

    async def send_template(
        self,
        to: str,
        *,
        template_name: str,
        language_code: str = "en",
        components: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Send an approved template message; returns the wamid."""
        template: Dict[str, Any] = {
            "name": template_name,
            "language": {"code": language_code},
        }
        if components:
            template["components"] = components
        body: Dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "template",
            "template": template,
        }
        data = await self._post(self._message_url(), body)
        return self._first_message_id(data)

    # ------------------------------------------------------------------ metadata

    async def fetch_profile(self, wa_id: str) -> Optional[Dict[str, Any]]:
        """Best-effort contact profile lookup (returns {} on failure)."""
        if not self._configured():
            return None
        url = f"{GRAPH_BASE}/{self.api_version}/{self.phone_number_id}/contacts"
        body = {"messaging_product": "whatsapp", "contacts": [{"wa_id": wa_id}]}
        try:
            data = await self._post(url, body)
            entries = data.get("contacts") or []
            return entries[0] if entries else None
        except WhatsAppCloudAPIError as e:
            log.warning("WhatsApp profile lookup failed for %s: %s", wa_id, e.message)
            return None

    # ------------------------------------------------------------------ internal

    def _first_message_id(self, data: Dict[str, Any]) -> str:
        messages = data.get("messages") or []
        if not messages or not messages[0].get("id"):
            raise WhatsAppCloudAPIError(
                "Cloud API response missing message id",
                retryable=True,
                payload=data,
            )
        return str(messages[0]["id"])

    async def _post(self, url: str, body: Dict[str, Any]) -> Dict[str, Any]:
        if not self._configured():
            raise WhatsAppCloudAPIError("WhatsApp Cloud API is not configured", retryable=False)
        try:
            r = await self._client.post(url, headers=self._headers(), json=body)
        except httpx.TransportError as e:
            raise WhatsAppCloudAPIError(f"network error: {e}", retryable=True) from e
        return self._parse_response(r.status_code, r.text)

    @staticmethod
    def _parse_response(status_code: int, text: str) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        try:
            data = __import__("json").loads(text) if text else {}
        except (ValueError, TypeError):
            pass

        error = data.get("error")
        if status_code == 200 and not error:
            return data

        api_code = None
        message = text[:400] or f"HTTP {status_code}"
        if isinstance(error, dict):
            api_code = error.get("code")
            message = str(error.get("message") or message)

        retryable = status_code in (429, 500, 502, 503, 504) or (
            isinstance(api_code, int) and api_code in (130429, 131056, 131045)
        )
        raise WhatsAppCloudAPIError(
            message,
            status_code=status_code,
            api_code=api_code,
            retryable=retryable,
            payload=data,
        )