# backend/app/sdk.py
"""SALAR Python SDK — minimal typed client for the SALAR API."""
import json
import logging
from typing import Any, Dict, List, Optional

import httpx

log = logging.getLogger(__name__)


class SalarAPIError(Exception):
    pass


class SalarClient:
    def __init__(self, base_url: str, token: Optional[str] = None, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout)
        self.token = token

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(self, method: str, path: str, **kwargs) -> Any:
        r = self._client.request(method, path, headers=self._headers(), **kwargs)
        if r.status_code >= 400:
            raise SalarAPIError(f"{method} {path} -> {r.status_code}: {r.text[:300]}")
        if not r.content:
            return None
        try:
            return r.json()
        except json.JSONDecodeError:
            return r.text

    def login(self, email: str, password: str) -> str:
        data = self._request("POST", "/api/auth/login", json={"email": email, "password": password})
        self.token = data.get("access_token") or data.get("token")
        if not self.token:
            raise SalarAPIError("login response missing access_token")
        return self.token

    def chat(self, content: str, *, conversation_id: str) -> Dict[str, Any]:
        return self._request("POST", "/api/chat", json={"conversation_id": conversation_id, "content": content})

    def search(self, query: str, *, limit: int = 10) -> List[Dict[str, Any]]:
        data = self._request("GET", "/api/search", params={"q": query, "limit": limit})
        return data.get("results", []) if isinstance(data, dict) else []

    def dashboard(self) -> Dict[str, Any]:
        return self._request("GET", "/api/dashboard")

    def list_tasks(self) -> List[Dict[str, Any]]:
        data = self._request("GET", "/api/tasks")
        return data if isinstance(data, list) else []

    def create_task(self, title: str, *, description: str = "", priority: str = "medium") -> Dict[str, Any]:
        return self._request("POST", "/api/tasks", json={"title": title, "description": description, "priority": priority})

    def close(self) -> None:
        self._client.close()
