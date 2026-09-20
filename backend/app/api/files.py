"""File manager endpoints — browse, read, write, upload, download, rename, move, delete."""

import hashlib
import hmac
import mimetypes
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from ..security import get_current_user
from ..models import User

router = APIRouter(prefix="/api/files", tags=["files"])


def _get_fm(request: Request, user: User):
    from ..services.file_manager import FileManager
    root = request.app.state.settings.storage_dir / "users" / user.id
    return FileManager(root=str(root))


class FileWriteRequest(BaseModel):
    path: str
    content: str


class FileRenameRequest(BaseModel):
    path: str
    new_name: str


class FileMoveRequest(BaseModel):
    src: str
    dest: str


class FileCopyRequest(BaseModel):
    src: str
    dest: str


@router.get("/list")
def list_files(path: str = "", sort: str = "name", desc: bool = False, request: Request = None, user: User = Depends(get_current_user)):
    return _get_fm(request, user).list_dir(path, sort_by=sort, sort_desc=desc)


@router.get("/tree")
def file_tree(path: str = "", depth: int = 2, request: Request = None, user: User = Depends(get_current_user)):
    return _get_fm(request, user).get_tree(path, depth=depth)


@router.get("/info")
def file_info(path: str, request: Request = None, user: User = Depends(get_current_user)):
    return _get_fm(request, user).file_info(path)


@router.get("/read")
def read_file(path: str, request: Request = None, user: User = Depends(get_current_user)):
    return _get_fm(request, user).read_file(path)


@router.post("/write")
def write_file(req: FileWriteRequest, request: Request = None, user: User = Depends(get_current_user)):
    result = _get_fm(request, user).write_file(req.path, req.content)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/mkdir")
def mkdir(path: str, request: Request = None, user: User = Depends(get_current_user)):
    return _get_fm(request, user).create_dir(path)


@router.post("/rename")
def rename(req: FileRenameRequest, request: Request = None, user: User = Depends(get_current_user)):
    return _get_fm(request, user).rename(req.path, req.new_name)


@router.post("/move")
def move(req: FileMoveRequest, request: Request = None, user: User = Depends(get_current_user)):
    return _get_fm(request, user).move(req.src, req.dest)


@router.post("/copy")
def copy_file(req: FileCopyRequest, request: Request = None, user: User = Depends(get_current_user)):
    return _get_fm(request, user).copy(req.src, req.dest)


@router.delete("/delete")
def delete_file(path: str, request: Request = None, user: User = Depends(get_current_user)):
    return _get_fm(request, user).delete(path)


@router.get("/search")
def search_files(q: str, path: str = "", request: Request = None, user: User = Depends(get_current_user)):
    results = _get_fm(request, user).search(q, path)
    return {"results": results, "count": len(results)}


@router.post("/upload")
async def upload_file(path: str = "", file: UploadFile = File(...), request: Request = None, user: User = Depends(get_current_user)):
    fm = _get_fm(request, user)
    # Sanitize the client filename: strip any directory components so a name
    # like "../secret.txt" or "..\\secret.txt" cannot escape the user sandbox.
    safe_name = Path(file.filename or "upload").name
    if not safe_name or safe_name in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid file name")
    try:
        target = fm._resolve(str(Path(path) / safe_name))
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    max_bytes = request.app.state.settings.max_upload_mb * 1024 * 1024
    size = 0
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(str(target), "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds {request.app.state.settings.max_upload_mb} MB limit",
                    )
                out.write(chunk)
    except HTTPException:
        target.unlink(missing_ok=True)
        raise
    except Exception as e:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "uploaded", "path": str(target.relative_to(fm.root)), "size": size}


@router.get("/download")
def download_file(path: str, request: Request = None, user: User = Depends(get_current_user)):
    fm = _get_fm(request, user)
    target = fm._resolve(path)
    if not target.exists() or target.is_dir():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(target), filename=target.name)


@router.get("/serve")
def serve_file(uid: str, path: str, exp: int, sig: str, request: Request):
    """Stream a user's file inline with a signed short-lived URL (no auth header needed)."""
    settings = request.app.state.settings
    expected = hmac.new(settings.jwt_secret.encode(), f"{uid}:{path}:{exp}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=403, detail="Invalid or expired link")
    if int(time.time()) > exp:
        raise HTTPException(status_code=403, detail="Link expired")
    root = settings.storage_dir / "users" / uid
    fm = FileManager(root=str(root))
    try:
        target = fm._resolve(path)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    if not target.exists() or target.is_dir():
        raise HTTPException(status_code=404, detail="File not found")
    mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    return FileResponse(str(target), media_type=mime)
