# backend/app/services/wallpapers.py
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class WallpaperManager:
    def __init__(self, storage_dir) -> None:
        self.storage_dir = Path(storage_dir)

    def save(self, image_bytes: bytes, *, name: str = "") -> Dict[str, Any]:
        folder = self.storage_dir / "wallpapers"
        folder.mkdir(parents=True, exist_ok=True)
        filename = f"{name or 'wallpaper'}_{uuid.uuid4().hex[:8]}.png"
        path = folder / filename
        path.write_bytes(image_bytes)
        return {"status": "ok", "filename": filename, "path": str(path), "size_bytes": len(image_bytes)}

    def list(self) -> List[Dict[str, Any]]:
        folder = self.storage_dir / "wallpapers"
        if not folder.exists():
            return []
        return [
            {"filename": f.name, "path": str(f), "size_bytes": f.stat().st_size}
            for f in sorted(folder.iterdir()) if f.is_file()
        ]
