"""File manager endpoints — browse, read, write, upload, download, rename, move, delete."""

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
def download_file(path: str, request: Request = None, user: User = Depends(get_current_user)):
    fm = _get_fm(request, user)
    target = fm._resolve(path)
    if not target.exists() or target.is_dir():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(target), filename=target.name)
