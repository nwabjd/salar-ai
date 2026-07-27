"""File manager endpoints — browse, read, write, upload, download, rename, move, delete."""

import os
import shutil
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from ..security import get_current_user
from ..models import User

router = APIRouter(prefix="/api/files", tags=["files"])

_file_manager = None


def _get_fm():
    global _file_manager
    if _file_manager is None:
        from ..services.file_manager import FileManager
        _file_manager = FileManager()
    return _file_manager


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
def list_files(path: str = "", sort: str = "name", desc: bool = False, user: User = Depends(get_current_user)):
    return _get_fm().list_dir(path, sort_by=sort, sort_desc=desc)


@router.get("/tree")
def file_tree(path: str = "", depth: int = 2, user: User = Depends(get_current_user)):
    return _get_fm().get_tree(path, depth=depth)


@router.get("/info")
def file_info(path: str, user: User = Depends(get_current_user)):
    return _get_fm().file_info(path)


@router.get("/read")
def read_file(path: str, user: User = Depends(get_current_user)):
    return _get_fm().read_file(path)


@router.post("/write")
def write_file(req: FileWriteRequest, user: User = Depends(get_current_user)):
    return _get_fm().write_file(req.path, req.content)


@router.post("/mkdir")
def mkdir(path: str, user: User = Depends(get_current_user)):
    return _get_fm().create_dir(path)


@router.post("/rename")
def rename(req: FileRenameRequest, user: User = Depends(get_current_user)):
    return _get_fm().rename(req.path, req.new_name)


@router.post("/move")
def move(req: FileMoveRequest, user: User = Depends(get_current_user)):
    return _get_fm().move(req.src, req.dest)


@router.post("/copy")
def copy_file(req: FileCopyRequest, user: User = Depends(get_current_user)):
    return _get_fm().copy(req.src, req.dest)


@router.delete("/delete")
def delete_file(path: str, user: User = Depends(get_current_user)):
    return _get_fm().delete(path)


@router.get("/search")
def search_files(q: str, path: str = "", user: User = Depends(get_current_user)):
    return {"results": _get_fm().search(q, path), "count": len(_get_fm().search(q, path))}


@router.post("/upload")
async def upload_file(path: str = "", file: UploadFile = File(...), user: User = Depends(get_current_user)):
    fm = _get_fm()
    target = fm._resolve(path) / file.filename
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(str(target), "wb") as f:
            content = await file.read()
            f.write(content)
        return {"status": "uploaded", "path": str(target.relative_to(fm.root)), "size": len(content)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download")
def download_file(path: str, user: User = Depends(get_current_user)):
    fm = _get_fm()
    target = fm._resolve(path)
    if not target.exists() or target.is_dir():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(target), filename=target.name)
