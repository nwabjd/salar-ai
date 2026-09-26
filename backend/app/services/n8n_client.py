"""n8n REST API client for SALAR's agent.

SALAR talks to a self-hosted n8n instance over its public REST API v1
(https://docs.n8n.io/connect/n8n-api/). The n8n engine is never vendored into
SALAR: the instance stays a separate service (local Docker sidecar or hosted),
which keeps SALAR inside n8n's Sustainable Use License (self-hosted / personal
use) instead of the "embed in a commercial product" case that requires a
commercial agreement.

Configuration resolution (priority order):
  1. Per-user registration: ``services.state.n8n_connections[user_id]``
     = {"base_url": ..., "api_key": ...} (set via POST /api/n8n/connect).
  2. Global environment: ``SALAR_N8N_BASE_URL`` + ``SALAR_N8N_API_KEY``
     (sidecar .env, Render dashboard, or docker compose).

Trigger semantics
-----------------
n8n's current public API exposes no "create execution" endpoint, so a workflow
is triggered through its **Webhook trigger** node when one exists (the reliable,
supported path). When the workflow has no webhook, we try the legacy
``POST /api/v1/executions`` endpoint that older n8n versions still ship.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

log = logging.getLogger(__name__)

_API_VERSION = "v1"
_DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_MAX_HEADER_BYTES = 500
_MAX_NODE_JSON_CHARS = 3000
_MAX_TOTAL_CHARS = 8000

WEBHOOK_NODE_TYPE = "n8n-nodes-base.webhook"


class N8NError(Exception):
    """Normalized n8n API error. ``.kind`` drives clean tool messages."""

    def __init__(self, message: str, kind: str = "upstream", status: Optional[int] = None):
        super().__init__(message)
        self.kind = kind  # invalid_config|auth|not_found|timeout|upstream
        self.status = status


def _normalize_base(base_url: Optional[str]) -> tuple[str, str]:
    """Return (origin, api_base) from a user-supplied base URL.

    Accepts either the instance origin (http://127.0.0.1:5678) or a URL that
    already includes /api/v1 (http://host/api/v1).
    """
    base = (base_url or "").strip().rstrip("/")
    if base.endswith(f"/api/{_API_VERSION}"):
        origin = base[: -len(f"/api/{_API_VERSION}")]
    else:
        origin = base
    return origin, f"{origin}/api/{_API_VERSION}"


def resolve_n8n_config(user_id: Optional[str] = None) -> Optional[Dict[str, str]]:
    """Per-user first, then global env settings. Returns None when unconfigured."""
    if user_id:
        try:
            from .state import n8n_connections

            per_user = n8n_connections.get(user_id)
            if per_user and per_user.get("base_url") and per_user.get("api_key"):
                return {"base_url": per_user["base_url"], "api_key": per_user["api_key"]}
        except Exception:  # pragma: no cover - defensive
            log.debug("n8n per-user state unavailable", exc_info=True)

    try:
        from ..config import Settings

        settings = Settings()
        base_url = (settings.n8n_base_url or "").strip()
        api_key = (settings.n8n_api_key or "").strip()
        if base_url and api_key:
            return {"base_url": base_url, "api_key": api_key}
    except Exception:  # pragma: no cover - defensive
        log.debug("n8n env settings unavailable", exc_info=True)
    return None


def get_n8n_client(user_id: Optional[str] = None, transport: Optional[httpx.BaseTransport] = None) -> Optional["N8nClient"]:
    """Build (or return None) a configured client. ``transport`` is for tests."""
    cfg = resolve_n8n_config(user_id)
    if not cfg:
        return None
    return N8nClient(cfg["base_url"], cfg["api_key"], transport=transport)


class N8nClient:
    """Async client for the n8n public REST API."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self._origin, self._api_base = _normalize_base(base_url)
        if not self._origin or not api_key:
            raise N8NError("n8n base URL and API key are required", kind="invalid_config")
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=self._api_base,
            headers={
                "X-N8N-API-KEY": api_key,
                "Accept": "application/json",
            },
            timeout=_DEFAULT_TIMEOUT,
            transport=transport,
        )

    # ------------------------------------------------------------------ #
    async def close(self) -> None:
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Any] = None,
    ) -> Dict[str, Any]:
        try:
            r = await self._client.request(method, path, params=params, json=json_body)
        except httpx.TimeoutException as exc:
            raise N8NError(f"Timed out talking to n8n at {self._origin}: {exc}", kind="timeout") from exc
        except httpx.HTTPError as exc:
            raise N8NError(f"Could not reach n8n at {self._origin}: {exc}", kind="upstream") from exc
        try:
            payload = r.json()
        except Exception:
            payload = {}
        if r.status_code in (401, 403):
            raise N8NError(
                f"n8n rejected the API key (HTTP {r.status_code}). Check X-N8N-API-KEY in "
                f"settings or SALAR_N8N_API_KEY.",
                kind="auth",
                status=r.status_code,
            )
        if r.status_code == 404:
            raise N8NError(f"n8n resource not found (HTTP 404) for {method} {path}", kind="not_found", status=r.status_code)
        if r.status_code >= 400:
            detail = json.dumps(payload, default=str)[:_MAX_HEADER_BYTES] if payload else r.text[:_MAX_HEADER_BYTES]
            raise N8NError(f"n8n returned HTTP {r.status_code}: {detail}", kind="upstream", status=r.status_code)
        return payload

    # -------------------------------------------------------------- workflows
    async def list_workflows(
        self,
        *,
        active: Optional[bool] = None,
        name: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Return a compact workflow summary plus webhook trigger info."""
        params: Dict[str, Any] = {"limit": min(max(limit, 1), 250)}
        if active is not None:
            params["active"] = "true" if active else "false"
        if name:
            params["name"] = name
        payload = await self._request("GET", "/workflows", params=params)
        workflows = []
        for wf in payload.get("data", []):
            workflows.append(self._summarize_workflow(wf))
        return {"workflows": workflows, "count": len(workflows), "base_url": self._origin}

    async def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        if not workflow_id:
            raise N8NError("workflow_id is required", kind="invalid_config")
        return await self._request("GET", f"/workflows/{workflow_id}")

    @staticmethod
    def _summarize_workflow(wf: Dict[str, Any]) -> Dict[str, Any]:
        summary = {
            "id": wf.get("id"),
            "name": wf.get("name"),
            "active": bool(wf.get("active")),
            "active_version_id": wf.get("activeVersionId"),
            "is_archived": bool(wf.get("isArchived")),
            "trigger_count": wf.get("triggerCount", 0),
            "tags": [t.get("name") for t in (wf.get("tags") or []) if t.get("name")],
        }
        webhooks = []
        for node in wf.get("nodes") or []:
            if (node or {}).get("type") == WEBHOOK_NODE_TYPE:
                params = node.get("parameters") or {}
                webhooks.append(
                    {
                        "node": node.get("name"),
                        "path": params.get("path"),
                        "http_method": (params.get("httpMethod") or "POST").upper(),
                    }
                )
        if webhooks:
            summary["webhook_triggers"] = webhooks
        return summary

    def _webhook_url(self, path: str) -> str:
        path = (path or "").strip()
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{self._origin}/webhook/{path.lstrip('/')}"

    # --------------------------------------------------------------- trigger
    async def trigger_workflow(self, workflow_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run a workflow. Webhook trigger first; legacy executions API fallback."""
        wf = await self.get_workflow(workflow_id)
        webhook = None
        for node in wf.get("nodes") or []:
            if (node or {}).get("type") == WEBHOOK_NODE_TYPE:
                webhook = node
                break

        if webhook is not None:
            params = webhook.get("parameters") or {}
            path = params.get("path") or ""
            method = (params.get("httpMethod") or "POST").upper()
            url = self._webhook_url(path)
            try:
                r = await self._client.request(method, url, json=payload or {})
            except httpx.HTTPError as exc:
                raise N8NError(f"Could not reach webhook {url}: {exc}", kind="upstream") from exc
            body = ""
            try:
                body = json.dumps(r.json(), default=str)[:_MAX_HEADER_BYTES]
            except Exception:
                body = r.text[:_MAX_HEADER_BYTES]
            if r.status_code >= 400:
                return {
                    **({"error": f"webhook returned HTTP {r.status_code}: {body}"}),
                    "workflow_id": workflow_id,
                    "webhook_url": url,
                }
            return {
                "triggered": "webhook",
                "workflow_id": workflow_id,
                "workflow_name": wf.get("name"),
                "webhook_url": url,
                "http_method": method,
                "status_code": r.status_code,
                "response": body[:_MAX_HEADER_BYTES] or "ok",
                "note": "Execution runs asynchronously. Poll n8n_workflow_result with this workflow_id "
                        "(or an execution id) to fetch the outcome.",
            }

        # Legacy execution API fallback (older n8n versions).
        try:
            result = await self._request(
                "POST",
                "/executions",
                json_body={"workflowId": workflow_id, "data": payload or {}, "includeData": False},
            )
        except N8NError as exc:
            if exc.status in (400, 404, 405) or exc.kind == "not_found":
                raise N8NError(
                    f"workflow '{workflow_id}' has no Webhook trigger and this n8n version does not "
                    f"expose POST /api/v1/executions ({exc}). Add a Webhook trigger node to the "
                    f"workflow so SALAR can run it.",
                    kind="upstream",
                ) from exc
            raise

        execution_id = (
            result.get("executionId")
            or result.get("execution_id")
            or result.get("id")
            or result.get("data", {}).get("executionId")
            if isinstance(result, dict)
            else None
        )
        return {
            "triggered": "execution_api",
            "workflow_id": workflow_id,
            "workflow_name": wf.get("name"),
            "execution_id": execution_id,
            "status": result.get("status") if isinstance(result, dict) else None,
            "note": "Poll n8n_workflow_result with the execution_id to fetch the outcome.",
        }

    # ------------------------------------------------------------ executions
    async def list_executions(
        self,
        *,
        workflow_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"limit": min(max(limit, 1), 250), "includeData": "false"}
        if workflow_id:
            params["workflowId"] = workflow_id
        if status:
            params["status"] = status
        payload = await self._request("GET", "/executions", params=params)
        return [
            {
                "id": e.get("id"),
                "status": e.get("status"),
                "mode": e.get("mode"),
                "started_at": e.get("startedAt"),
                "stopped_at": e.get("stoppedAt"),
                "workflow_id": e.get("workflowId"),
            }
            for e in payload.get("data", [])
        ]

    async def get_execution(self, execution_id: str, include_data: bool = True) -> Dict[str, Any]:
        params = {"includeData": "true" if include_data else "false"}
        payload = await self._request("GET", f"/executions/{execution_id}", params=params)
        summary = {
            "id": payload.get("id"),
            "status": payload.get("status"),
            "mode": payload.get("mode"),
            "workflow_id": payload.get("workflowId"),
            "started_at": payload.get("startedAt"),
            "stopped_at": payload.get("stoppedAt"),
            "finished": bool(payload.get("finished")),
        }
        if include_data and isinstance(payload.get("data"), dict):
            summary["outputs"] = self._extract_outputs(payload["data"])
        if summary.get("status") == "error":
            summary["error"] = self._extract_error(payload.get("data"))
        return summary

    async def health(self) -> Dict[str, Any]:
        try:
            page = await self.list_workflows(limit=1)
            return {
                "connected": True,
                "base_url": self._origin,
                "workflow_count_first_page": page.get("count", 0),
            }
        except N8NError as exc:
            return {"connected": False, "base_url": self._origin, "error": f"{exc.kind}: {exc}"}

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _extract_outputs(data: Dict[str, Any]) -> Dict[str, Any]:
        """Compact summary of the last item each node emitted."""
        run_data = (data.get("result_data") or {}).get("runData") or {}
        last_node = (data.get("result_data") or {}).get("lastNodeExecuted")
        outputs: Dict[str, Any] = {}
        total = 0
        for node_name, runs in run_data.items():
            if not isinstance(runs, list) or not runs:
                continue
            if not isinstance(runs[-1], dict):
                continue
            main = (runs[-1].get("data") or {}).get("main") or []
            if not main or not isinstance(main[-1], list):
                continue
            item = main[-1][-1] if main[-1] else None
            if not isinstance(item, dict):
                continue
            value = item.get("json") if "json" in item else item
            try:
                text = json.dumps(value, default=str)
            except Exception:
                text = str(value)
            if len(text) > _MAX_NODE_JSON_CHARS:
                text = text[:_MAX_NODE_JSON_CHARS] + "…(truncated)"
            outputs[node_name] = text
            total += len(text)
            if total > _MAX_TOTAL_CHARS:
                break
        return {"last_node_executed": last_node, "node_outputs": outputs}

    @staticmethod
    def _extract_error(data: Optional[Dict[str, Any]]) -> str:
        if not isinstance(data, dict):
            return "workflow execution failed (no detail available)"
        error = (data.get("result_data") or {}).get("error")
        if isinstance(error, dict):
            msg = error.get("message") or error.get("msg") or ""
            node = error.get("node", {}).get("name") if isinstance(error.get("node"), dict) else None
            return f"{node + ': ' if node else ''}{msg}".strip() or "workflow execution failed"
        return str(error) or "workflow execution failed"