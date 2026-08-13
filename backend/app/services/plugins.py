# backend/app/services/plugins.py
import json
import logging
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import select

from ..models import Plugin, token_id, utcnow

log = logging.getLogger(__name__)

# Plugin command registry: {"plugin_name.command_name": callable(db, args) -> dict}
COMMAND_REGISTRY: Dict[str, Callable[..., Dict[str, Any]]] = {}


def register_command(plugin_name: str, command_name: str) -> Callable:
    """Decorator registering a plugin command handler."""

    def decorator(fn):
        COMMAND_REGISTRY[f"{plugin_name}.{command_name}"] = fn
        return fn

    return decorator


class PluginError(Exception):
    pass


class PluginManager:
    def __init__(self, db) -> None:
        self.db = db

    def install(self, user_id: str, manifest: Dict[str, Any]) -> Plugin:
        name = manifest.get("name", "").strip()
        if not name:
            raise PluginError("manifest must include a name")
        existing = self.db.scalar(select(Plugin).where(Plugin.user_id == user_id, Plugin.name == name))
        if existing:
            existing.version = manifest.get("version", existing.version)
            existing.description = manifest.get("description", existing.description)
            existing.author = manifest.get("author", existing.author)
            existing.manifest_json = json.dumps(manifest)
            return existing
        plugin = Plugin(
            id=token_id(), user_id=user_id, name=name,
            version=manifest.get("version", "0.1.0"),
            description=manifest.get("description", ""),
            author=manifest.get("author", ""),
            manifest_json=json.dumps(manifest),
            enabled=True, created_at=utcnow(), updated_at=utcnow(),
        )
        self.db.add(plugin)
        self.db.flush()
        return plugin

    def list(self, user_id: str) -> List[Dict[str, Any]]:
        rows = self.db.scalars(select(Plugin).where(Plugin.user_id == user_id).order_by(Plugin.created_at)).all()
        return [self._serialize(p) for p in rows]

    def uninstall(self, user_id: str, plugin_id: str) -> bool:
        p = self.db.get(Plugin, plugin_id)
        if p is None or p.user_id != user_id:
            return False
        self.db.delete(p)
        return True

    def toggle(self, user_id: str, plugin_id: str, enabled: bool) -> Optional[Dict[str, Any]]:
        p = self.db.get(Plugin, plugin_id)
        if p is None or p.user_id != user_id:
            return None
        p.enabled = enabled
        return self._serialize(p)

    def commands(self, user_id: str) -> List[Dict[str, Any]]:
        """All enabled plugin commands available to the user."""
        commands = []
        for p in self.list(user_id):
            if not p["enabled"]:
                continue
            manifest = p["manifest"]
            for cmd in manifest.get("commands", []):
                commands.append({
                    "plugin": p["name"],
                    "name": cmd.get("name", ""),
                    "description": cmd.get("description", ""),
                })
        return commands

    def execute(self, user_id: str, plugin_name: str, command_name: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        plugin = self.db.scalar(select(Plugin).where(Plugin.user_id == user_id, Plugin.name == plugin_name))
        if plugin is None:
            raise PluginError("plugin not installed")
        if not plugin.enabled:
            raise PluginError("plugin is disabled")
        key = f"{plugin_name}.{command_name}"
        handler = COMMAND_REGISTRY.get(key)
        if handler is None:
            raise PluginError(f"command '{key}' not registered")
        return handler(self.db, args or {})

    def marketplace(self) -> List[Dict[str, Any]]:
        """Curated catalog of plugins users can install."""
        return [
            {"name": "translator", "version": "0.1.0", "description": "Translate text between languages via a plugin command.", "author": "SALAR Team", "commands": [{"name": "translate", "description": "Translate text"}]},
            {"name": "url-shortener", "version": "0.1.0", "description": "Shorten URLs from chat.", "author": "SALAR Team", "commands": [{"name": "shorten", "description": "Shorten a URL"}]},
            {"name": "weather-lite", "version": "0.1.0", "description": "Lightweight weather lookup.", "author": "SALAR Team", "commands": [{"name": "forecast", "description": "Get weather forecast"}]},
        ]

    def _serialize(self, p: Plugin) -> Dict[str, Any]:
        return {
            "id": p.id, "name": p.name, "version": p.version, "description": p.description,
            "author": p.author, "enabled": p.enabled,
            "manifest": json.loads(p.manifest_json or "{}"),
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
