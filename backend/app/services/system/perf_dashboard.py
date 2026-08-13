# backend/app/services/system/perf_dashboard.py
import logging
from typing import Any, Dict

log = logging.getLogger(__name__)


class PerformanceDashboard:
    def snapshot(self) -> Dict[str, Any]:
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            return {
                "status": "ok",
                "cpu": {"percent": cpu, "cores": psutil.cpu_count(logical=True)},
                "memory": {"percent": mem.percent, "used_gb": round(mem.used / 1e9, 1), "total_gb": round(mem.total / 1e9, 1)},
                "disk": {"percent": disk.percent, "free_gb": round(disk.free / 1e9, 1), "total_gb": round(disk.total / 1e9, 1)},
                "battery": self._battery(),
                "uptime_seconds": self._uptime(),
            }
        except Exception as exc:
            return {"status": "error", "detail": str(exc)}

    def _battery(self):
        try:
            import psutil
            b = psutil.sensors_battery()
            if b is None:
                return None
            return {"percent": b.percent, "plugged": b.power_plugged}
        except Exception:
            return None

    def _uptime(self):
        try:
            import psutil
            return int(psutil.boot_time() and __import__("time").time() - psutil.boot_time())
        except Exception:
            return None
