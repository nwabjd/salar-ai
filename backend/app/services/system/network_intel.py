# backend/app/services/system/network_intel.py
import logging
import socket
from typing import Any, Dict, List

log = logging.getLogger(__name__)


class NetworkIntelligence:
    def local_info(self) -> Dict[str, Any]:
        try:
            hostname = socket.gethostname()
            ips = set()
            try:
                for info in socket.getaddrinfo(hostname, None):
                    ip = info[4][0]
                    if ip and not ip.startswith("127."):
                        ips.add(ip)
            except Exception:
                pass
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                primary = s.getsockname()[0]
                s.close()
            except Exception:
                primary = None
            return {"status": "ok", "hostname": hostname, "ip_addresses": sorted(ips), "primary_ip": primary}
        except Exception as exc:
            return {"status": "error", "detail": str(exc)}

    def ping(self, host: str = "8.8.8.8") -> Dict[str, Any]:
        try:
            import subprocess
            r = subprocess.run(["ping", "-n", "1", "-w", "2000", host], capture_output=True, text=True, timeout=6)
            return {"status": "ok" if r.returncode == 0 else "unreachable", "host": host, "output": r.stdout[:500]}
        except Exception as exc:
            return {"status": "error", "detail": str(exc)}
