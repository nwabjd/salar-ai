"""Registered background job handlers for the intelligence engine.

Importing this module registers handlers on the shared registry (side effect).
"""

import asyncio
import logging
from typing import Any, Dict

from ...config import Settings
from ..state import email_accounts
from .contracts import JobContext, JobRegistry

log = logging.getLogger(__name__)


def register_all(registry: JobRegistry) -> None:
    """Attach all intel handlers to a registry."""

    @registry.register("intel.email_watch")
    async def email_watch(ctx: JobContext) -> Dict[str, Any]:
        from ..intel.email_watch import scan_email_account

        cfg = email_accounts.get(ctx.user_id)
        if not cfg:
            return {"status": "skipped", "reason": "no email account configured"}
        limit = getattr(ctx.settings, "intel_email_watch_limit", 50)
        # IMAP is blocking — run in a thread.
        result = await asyncio.to_thread(scan_email_account, ctx.db, ctx.user_id, cfg, limit=int(limit))
        result["status"] = "ok"
        return result

    @registry.register("brief.morning")
    async def morning_brief(ctx: JobContext) -> Dict[str, Any]:
        from ..intel.briefing import build_morning_brief

        brief = build_morning_brief(ctx.db, ctx.user_id)
        return {"status": "ok", "brief": brief}

    @registry.register("world.sync")
    async def world_sync(ctx: JobContext) -> Dict[str, Any]:
        """Mirror the fragmented memory stores into the world graph and ingest
        connected sources (calendar, devices). Runs periodically."""
        from ..world_model import MemorySyncService, WorldGraph, WorldIngestor

        graph = WorldGraph(ctx.db)
        syncer = MemorySyncService(ctx.db)
        counts = syncer.sync_all(ctx.user_id)
        syncer.sync_relations(ctx.user_id)

        ingestor = WorldIngestor(graph)
        extra = {"calendar": 0, "devices": 0}

        calendar_payload = ctx.input_data or {}
        if calendar_payload.get("calendar_events"):
            for event in calendar_payload["calendar_events"]:
                if ingestor.ingest_calendar_event(ctx.user_id, event):
                    extra["calendar"] += 1

        from ...models import Device
        from sqlalchemy import select
        devices = ctx.db.scalars(
            select(Device).where(Device.user_id == ctx.user_id)
        ).all()
        for device in devices:
            if ingestor.ingest_device(ctx.user_id, {
                "name": device.name,
                "id": device.id,
                "platform": device.platform or "",
            }):
                extra["devices"] += 1

        ctx.db.commit()
        return {"status": "ok", "memories": counts, "extra": extra}
