# backend/app/services/ar_status.py
import logging
from typing import Any, Dict

log = logging.getLogger(__name__)


class ARStatus:
    def check(self) -> Dict[str, Any]:
        """Report device AR/3D capability hints and backend support status."""
        return {
            "status": "ok",
            "supported": {
                "ar_web": False,
                "three_d": True,
                "gltf_export": True,
            },
            "formats": ["gltf", "glb"],
            "note": "AR requires a capable mobile device; 3D/GLTF supported server-side.",
        }
