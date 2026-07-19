from typing import Dict, List

import httpx


class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout: float = 45.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={"model": self.model, "messages": messages, "stream": False},
            )
            response.raise_for_status()
            return response.json()["message"]["content"].strip()

