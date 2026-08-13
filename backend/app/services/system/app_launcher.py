# backend/app/services/system/app_launcher.py
import logging
from typing import Any, Dict, List

log = logging.getLogger(__name__)

# Common Windows/macOS app aliases to display names
APP_ALIASES = {
    "vscode": ["Code", "Visual Studio Code"],
    "chrome": ["Google Chrome", "Chrome"],
    "edge": ["Microsoft Edge", "msedge"],
    "firefox": ["Firefox", "Mozilla Firefox"],
    "notepad": ["Notepad", "notepad.exe"],
    "terminal": ["Windows Terminal", "Terminal", "cmd"],
    "explorer": ["File Explorer", "explorer.exe"],
    "settings": ["Settings", "System Settings"],
    "spotify": ["Spotify", "spotify.exe"],
    "slack": ["Slack", "slack.exe"],
    "discord": ["Discord", "Discord.exe"],
}


class AppLauncher:
    def search(self, query: str) -> List[Dict[str, Any]]:
        q = query.strip().lower()
        if not q:
            return []
        results = []
        for alias, names in APP_ALIASES.items():
            if q in alias or any(q in n.lower() for n in names):
                results.append({"alias": alias, "name": names[0], "aliases": names})
        return results

    def suggest(self) -> List[Dict[str, Any]]:
        return [
            {"alias": "vscode", "name": "Visual Studio Code"},
            {"alias": "chrome", "name": "Google Chrome"},
            {"alias": "explorer", "name": "File Explorer"},
            {"alias": "terminal", "name": "Terminal"},
            {"alias": "notepad", "name": "Notepad"},
        ]
