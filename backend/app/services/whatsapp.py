import logging
from typing import Any, Dict, List, Optional

import httpx

log = logging.getLogger(__name__)

DEFAULT_BRIDGE_URL = "http://127.0.0.1:3100"


class WhatsAppClient:
    def __init__(self, bridge_url: str = DEFAULT_BRIDGE_URL):
        self.bridge_url = bridge_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(connect=5, read=15, write=5, pool=5))

    async def close(self):
        await self._client.aclose()

    def _headers(self, user_id: str) -> dict:
        return {"X-User-Id": str(user_id)}

    async def get_status(self, user_id: str) -> Dict[str, Any]:
        try:
            r = await self._client.get(f"{self.bridge_url}/status", headers=self._headers(user_id))
            return r.json()
        except Exception as e:
            log.warning("WhatsApp bridge status failed: %s", e)
            return {"status": "unreachable", "error": str(e)}

    async def get_qr(self, user_id: str) -> Optional[str]:
        try:
            r = await self._client.get(f"{self.bridge_url}/qr", headers=self._headers(user_id))
            data = r.json()
            return data.get("qr")
        except Exception as e:
            log.warning("WhatsApp QR fetch failed: %s", e)
            return None

    async def send_message(self, to: str = None, phone: str = None, text: str = "", user_id: str = None) -> Dict[str, Any]:
        if not text:
            return {"error": "text is required"}
        body = {"text": text}
        if to:
            body["to"] = to
        elif phone:
            body["phone"] = phone
        else:
            return {"error": "to or phone is required"}
        headers = self._headers(user_id) if user_id else {}
        try:
            r = await self._client.post(f"{self.bridge_url}/send", json=body, headers=headers)
            return r.json()
        except Exception as e:
            log.error("WhatsApp send failed: %s", e)
            return {"error": str(e)}

    async def get_chats(self, user_id: str) -> List[Dict[str, Any]]:
        try:
            r = await self._client.get(f"{self.bridge_url}/chats", headers=self._headers(user_id))
            return r.json()
        except Exception as e:
            log.warning("WhatsApp chats fetch failed: %s", e)
            return []

    async def get_messages(self, jid: str, limit: int = 20, user_id: str = None) -> List[Dict[str, Any]]:
        try:
            r = await self._client.get(f"{self.bridge_url}/messages/{jid}", params={"limit": limit}, headers=self._headers(user_id))
            return r.json()
        except Exception as e:
            log.warning("WhatsApp messages fetch failed: %s", e)
            return []

    async def get_contacts(self, user_id: str) -> List[Dict[str, Any]]:
        try:
            r = await self._client.get(f"{self.bridge_url}/contacts", headers=self._headers(user_id))
            return r.json()
        except Exception as e:
            log.warning("WhatsApp contacts fetch failed: %s", e)
            return []

    async def logout(self, user_id: str) -> Dict[str, Any]:
        try:
            r = await self._client.post(f"{self.bridge_url}/logout", headers=self._headers(user_id))
            return r.json()
        except Exception as e:
            log.warning("WhatsApp logout failed: %s", e)
            return {"error": str(e)}
