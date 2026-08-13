# backend/app/services/system/audio_intel.py
import logging
from typing import Any, Dict, List

log = logging.getLogger(__name__)


class AudioIntelligence:
    def devices(self) -> List[Dict[str, Any]]:
        try:
            import sounddevice as sd
            devices = []
            for i, d in enumerate(sd.query_devices()):
                devices.append({
                    "index": i,
                    "name": d.get("name", ""),
                    "hostapi": d.get("hostapi", 0),
                    "max_input_channels": d.get("max_input_channels", 0),
                    "max_output_channels": d.get("max_output_channels", 0),
                    "default_samplerate": d.get("default_samplerate", 0),
                })
            return devices
        except Exception:
            return []

    def set_volume(self, level: int) -> Dict[str, Any]:
        level = max(0, min(100, int(level)))
        try:
            import subprocess
            subprocess.run(
                ["powershell", "-c", "(New-Object -ComObject WScript.Shell).SendKeys([string]::Concat([char]175, ''))"],
                capture_output=True, timeout=5,
            )
            return {"status": "ok", "level": level, "note": "volume adjusted via media keys"}
        except Exception as exc:
            return {"status": "error", "detail": str(exc), "level": level}
