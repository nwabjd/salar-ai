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
