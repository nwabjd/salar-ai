"""System monitor endpoints — real-time CPU, RAM, disk, network."""

import asyncio
import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from ..security import require_admin
from ..models import User

router = APIRouter(prefix="/api/monitor", tags=["monitor"])


@router.get("/snapshot")
def snapshot(user: User = Depends(require_admin)):
    """Get a single system snapshot."""
    from ..services.monitor import get_snapshot
    return get_snapshot()


@router.get("/stream")
async def stream(user: User = Depends(require_admin)):
    """SSE stream of system snapshots every 2 seconds."""
    from ..services.monitor import monitor_stream

    async def event_generator():
        try:
            async for snapshot in monitor_stream(interval=2.0):
                yield f"data: {json.dumps(snapshot)}\n\n"
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "X-Accel-Buffering": "no",
            "Content-Encoding": "identity",
        },
    )


@router.get("/processes")
def processes(user: User = Depends(require_admin)):
    """List all processes with CPU/memory usage."""
    import psutil
    procs = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
        try:
            info = proc.info
            procs.append({
                "pid": info["pid"],
                "name": info["name"],
                "cpu_percent": round(info.get("cpu_percent", 0) or 0, 1),
                "memory_percent": round(info.get("memory_percent", 0) or 0, 1),
                "status": info.get("status", "unknown"),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procs.sort(key=lambda p: p["cpu_percent"], reverse=True)
    return {"processes": procs[:100], "total": len(procs)}
