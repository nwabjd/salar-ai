# backend/app/services/file_organizer.py
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

EXTENSION_FOLDERS = {
    "images": {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico"},
    "documents": {".pdf", ".docx", ".doc", ".txt", ".md", ".xlsx", ".xls", ".pptx", ".csv"},
    "archives": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "code": {".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".json", ".yml", ".yaml", ".go", ".rs", ".java", ".cpp", ".c"},
    "media": {".mp3", ".wav", ".mp4", ".mov", ".mkv", ".webm", ".flac"},
    "installers": {".exe", ".msi", ".dmg", ".apk", ".deb", ".rpm"},
    "other": set(),
}


class FileOrganizer:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)

    def _folder_for(self, filename: str) -> str:
        ext = Path(filename).suffix.lower()
        for folder, exts in EXTENSION_FOLDERS.items():
            if ext in exts:
                return folder
        return "other"

    def plan(self, directory: Optional[Path] = None) -> List[Dict[str, Any]]:
        """Dry-run: list files and target folders without moving."""
        root = directory or self.base_dir
        plan = []
        if not root.exists():
            return plan
        for item in sorted(root.iterdir()):
            if item.is_file():
                plan.append({"file": item.name, "current": str(item), "target_folder": self._folder_for(item.name)})
        return plan

    def apply(self, directory: Optional[Path] = None, *, move: bool = True) -> Dict[str, Any]:
        root = directory or self.base_dir
        plan = self.plan(root)
        moved, errors = [], []
        for entry in plan:
            src = Path(entry["current"])
            dest_dir = root / entry["target_folder"]
            dest = dest_dir / src.name
            try:
                if not dest_dir.exists():
                    dest_dir.mkdir(parents=True, exist_ok=True)
                if move:
                    if dest.exists():
                        dest = dest_dir / f"{src.stem}_dup{src.suffix}"
                    shutil.move(str(src), str(dest))
                moved.append({"from": entry["current"], "to": str(dest)})
            except Exception as exc:
                errors.append({"file": entry["file"], "error": str(exc)})
        return {"moved": moved, "errors": errors, "planned": len(plan)}
