# backend/app/services/system/media_controller.py
import logging
from typing import Any, Dict

log = logging.getLogger(__name__)

VALID_ACTIONS = {"play", "pause", "play_pause", "next", "previous", "stop", "mute", "unmute", "volume_up", "volume_down"}

_MEDIA_KEYS = {
    "play": "{MEDIA_PLAY}",
    "pause": "{MEDIA_PAUSE}",
    "play_pause": "{MEDIA_PLAY_PAUSE}",
    "next": "{MEDIA_NEXT}",
    "previous": "{MEDIA_PREV}",
    "stop": "{MEDIA_STOP}",
    "mute": "{VOLUME_MUTE}",
    "unmute": "{VOLUME_MUTE}",
    "volume_up": "{VOLUME_UP}",
    "volume_down": "{VOLUME_DOWN}",
}


class MediaController:
    def control(self, action: str) -> Dict[str, Any]:
        action = (action or "").lower()
        if action not in VALID_ACTIONS:
            return {"status": "error", "detail": f"invalid action: {action}", "valid": sorted(VALID_ACTIONS)}
        try:
            import subprocess
            keys = _MEDIA_KEYS.get(action, "{MEDIA_PLAY_PAUSE}")
            subprocess.run(
                ["powershell", "-c", f"(New-Object -ComObject WScript.Shell).SendKeys('{keys}')"],
                capture_output=True, timeout=5,
            )
            return {"status": "ok", "action": action}
        except Exception as exc:
            return {"status": "error", "detail": str(exc), "action": action}

    def now_playing(self) -> Dict[str, Any]:
        try:
            return {"status": "ok", "detail": "Player metadata unavailable on this platform", "platform": "windows"}
        except Exception as exc:
            return {"status": "ok", "detail": str(exc)}
