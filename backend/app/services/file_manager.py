"""File manager service — browse, upload, download, rename, move, delete, search files."""

import os
import shutil
import mimetypes
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

DEFAULT_ROOT: Optional[Path] = None


class FileManager:
    def __init__(self, root: str = None):
        root_path = Path(root) if root else (DEFAULT_ROOT or Path.home())
        self.root = root_path
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        """Resolve and validate a path — prevent traversal attacks."""
        target = (self.root / path).resolve() if path else self.root
        try:
            target.relative_to(self.root)
        except ValueError:
            raise ValueError(f"Access denied: path outside root")
        return target

    def _safe(self, path: Path) -> Dict[str, Any]:
        """Convert a Path to a safe dict for API responses."""
        try:
            stat = path.stat()
            is_dir = path.is_dir()
            mime = mimetypes.guess_type(path.name)[0] if not is_dir else "inode/directory"
            return {
                "name": path.name,
                "path": str(path.relative_to(self.root)),
                "is_dir": is_dir,
                "size": stat.st_size if not is_dir else 0,
                "size_human": self._human_size(stat.st_size) if not is_dir else "-",
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "mime": mime or "application/octet-stream",
                "extension": path.suffix.lower() if not is_dir else "",
            }
        except Exception as e:
            return {"name": path.name, "path": str(path.relative_to(self.root)), "error": str(e)}

    def _human_size(self, size: int) -> str:
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.1f} {unit}" if unit != "B" else f"{size} B"
            size /= 1024
        return f"{size:.1f} PB"

    def list_dir(self, path: str = "", sort_by: str = "name", sort_desc: bool = False) -> Dict[str, Any]:
        """List directory contents."""
        target = self._resolve(path)
        if not target.exists():
            return {"error": f"Directory not found: {path}"}
        if not target.is_dir():
            return {"error": f"Not a directory: {path}"}

        items = []
        for entry in sorted(target.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            if entry.name.startswith(".") and entry.name not in (".env", ".env.local"):
                continue  # Skip hidden files
            items.append(self._safe(entry))

        # Sort
        sort_key = sort_by if sort_by in ("name", "size", "modified", "extension") else "name"
        items.sort(key=lambda x: (x.get("is_dir", False), x.get(sort_key, "")), reverse=sort_desc)

        return {
            "path": path or "/",
            "items": items,
            "count": len(items),
            "parent": str(Path(path).parent) if path and path != "/" else None,
        }

    def read_file(self, path: str, max_size: int = 1_000_000) -> Dict[str, Any]:
        """Read file content (text files only)."""
        target = self._resolve(path)
        if not target.exists():
            return {"error": f"File not found: {path}"}
        if target.is_dir():
            return {"error": f"Cannot read a directory: {path}"}
        if target.stat().st_size > max_size:
            return {"error": f"File too large ({self._human_size(target.stat().st_size)}). Max: {self._human_size(max_size)}"}

        try:
            content = target.read_text(encoding="utf-8", errors="replace")
            return {
                "path": path,
                "name": target.name,
                "size": target.stat().st_size,
                "content": content,
                "mime": mimetypes.guess_type(target.name)[0] or "text/plain",
            }
        except Exception as e:
            return {"error": str(e)}

    def write_file(self, path: str, content: str) -> Dict[str, Any]:
        """Write content to a file."""
        try:
            target = self._resolve(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return {"status": "written", "path": path, "size": len(content)}
        except Exception as e:
            return {"error": str(e)}

    def create_dir(self, path: str) -> Dict[str, Any]:
        """Create a directory."""
        target = self._resolve(path)
        try:
            target.mkdir(parents=True, exist_ok=True)
            return {"status": "created", "path": path}
        except Exception as e:
            return {"error": str(e)}

    def rename(self, old_path: str, new_name: str) -> Dict[str, Any]:
        """Rename a file or directory."""
        old = self._resolve(old_path)
        if not old.exists():
            return {"error": f"Not found: {old_path}"}
        new = (old.parent / new_name).resolve()
        try:
            new.relative_to(self.root)
        except ValueError:
            return {"error": "Access denied: path outside root"}
        try:
            old.rename(new)
            return {"status": "renamed", "old_path": old_path, "new_path": str(new.relative_to(self.root))}
        except Exception as e:
            return {"error": str(e)}

    def move(self, src_path: str, dest_dir: str) -> Dict[str, Any]:
        """Move a file or directory."""
        src = self._resolve(src_path)
        dest = self._resolve(dest_dir)
        if not src.exists():
            return {"error": f"Not found: {src_path}"}
        if not dest.is_dir():
            return {"error": f"Destination is not a directory: {dest_dir}"}
        try:
            shutil.move(str(src), str(dest / src.name))
            return {"status": "moved", "from": src_path, "to": str((dest / src.name).relative_to(self.root))}
        except Exception as e:
            return {"error": str(e)}

    def copy(self, src_path: str, dest_dir: str) -> Dict[str, Any]:
        """Copy a file or directory."""
        src = self._resolve(src_path)
        dest = self._resolve(dest_dir)
        if not src.exists():
            return {"error": f"Not found: {src_path}"}
        try:
            if src.is_dir():
                shutil.copytree(str(src), str(dest / src.name))
            else:
                shutil.copy2(str(src), str(dest / src.name))
            return {"status": "copied", "from": src_path, "to": str((dest / src.name).relative_to(self.root))}
        except Exception as e:
            return {"error": str(e)}

    def delete(self, path: str) -> Dict[str, Any]:
        """Delete a file or directory."""
        target = self._resolve(path)
        if not target.exists():
            return {"error": f"Not found: {path}"}
        try:
            if target.is_dir():
                shutil.rmtree(str(target))
            else:
                target.unlink()
            return {"status": "deleted", "path": path}
        except Exception as e:
            return {"error": str(e)}

    def search(self, query: str, path: str = "", max_results: int = 50) -> List[Dict[str, Any]]:
        """Search for files by name."""
        root = self._resolve(path)
        if not root.exists():
            return []
        query_lower = query.lower()
        results = []
        for dirpath, dirnames, filenames in os.walk(str(root)):
            for name in filenames + dirnames:
                if query_lower in name.lower():
                    full = Path(dirpath) / name
                    try:
                        results.append(self._safe(full))
                    except Exception:
                        continue
                    if len(results) >= max_results:
                        return results
        return results

    def file_info(self, path: str) -> Dict[str, Any]:
        """Get detailed info about a file."""
        target = self._resolve(path)
        if not target.exists():
            return {"error": f"Not found: {path}"}
        info = self._safe(target)
        if target.is_dir():
            try:
                info["item_count"] = len(list(target.iterdir()))
            except Exception:
                info["item_count"] = 0
        else:
            mime = mimetypes.guess_type(target.name)[0] or ""
            info["is_text"] = mime.startswith("text/") or target.suffix.lower() in (
                ".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".yaml", ".yml", ".toml",
                ".md", ".txt", ".html", ".css", ".xml", ".csv", ".sql", ".sh", ".bat",
                ".env", ".gitignore", ".dockerfile", ".rs", ".go", ".java", ".c", ".cpp",
                ".h", ".rb", ".php", ".swift", ".kt", ".scala", ".r", ".lua", ".vim",
            )
            info["is_image"] = mime.startswith("image/")
            info["is_audio"] = mime.startswith("audio/")
            info["is_video"] = mime.startswith("video/")
            info["is_pdf"] = mime == "application/pdf"
        return info

    def get_tree(self, path: str = "", depth: int = 2) -> Dict[str, Any]:
        """Get a directory tree (nested structure)."""
        target = self._resolve(path)
        if not target.exists() or not target.is_dir():
            return {"error": "Invalid path"}

        def _build(p: Path, d: int) -> dict:
            node = {"name": p.name, "path": str(p.relative_to(self.root)), "is_dir": True, "children": []}
            if d <= 0:
                node["has_children"] = any(p.iterdir()) if p.is_dir() else False
                return node
            try:
                for child in sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
                    if child.name.startswith("."):
                        continue
                    if child.is_dir():
                        node["children"].append(_build(child, d - 1))
                    else:
                        node["children"].append({"name": child.name, "path": str(child.relative_to(self.root)), "is_dir": False})
            except PermissionError:
                pass
            return node

        return _build(target, depth)
