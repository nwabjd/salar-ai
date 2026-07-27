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

    async def get_status(self) -> Dict[str, Any]:
        try:
            r = await self._client.get(f"{self.bridge_url}/status")
            return r.json()
        except Exception as e:
            log.warning("WhatsApp bridge status failed: %s", e)
            return {"status": "unreachable", "error": str(e)}

    async def get_qr(self) -> Optional[str]:
        try:
            r = await self._client.get(f"{self.bridge_url}/qr")
            data = r.json()
            return data.get("qr")
        except Exception as e:
            log.warning("WhatsApp QR fetch failed: %s", e)
            return None

    async def send_message(self, to: str = None, phone: str = None, text: str = "") -> Dict[str, Any]:
        if not text:
            return {"error": "text is required"}
        body = {"text": text}
        if to:
            body["to"] = to
        elif phone:
            body["phone"] = phone
        else:
            return {"error": "to or phone is required"}
        try:
            r = await self._client.post(f"{self.bridge_url}/send", json=body)
            return r.json()
        except Exception as e:
            log.error("WhatsApp send failed: %s", e)
            return {"error": str(e)}

    async def get_chats(self) -> List[Dict[str, Any]]:
        try:
            r = await self._client.get(f"{self.bridge_url}/chats")
            return r.json()
        except Exception as e:
            log.warning("WhatsApp chats fetch failed: %s", e)
            return []

    async def get_messages(self, jid: str, limit: int = 20) -> List[Dict[str, Any]]:
        try:
            r = await self._client.get(f"{self.bridge_url}/messages/{jid}", params={"limit": limit})
            return r.json()
        except Exception as e:
            log.warning("WhatsApp messages fetch failed: %s", e)
            return []

    async def get_contacts(self) -> List[Dict[str, Any]]:
        try:
            r = await self._client.get(f"{self.bridge_url}/contacts")
            return r.json()
        except Exception as e:
            log.warning("WhatsApp contacts fetch failed: %s", e)
            return []
