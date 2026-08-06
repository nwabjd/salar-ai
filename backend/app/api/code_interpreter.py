"""Code interpreter endpoints — execute Python/JS snippets in a per-user sandbox."""

import logging
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from ..security import get_current_user
from ..models import User

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/code", tags=["code"])


def _get_interp(request: Request, user: User):
    from ..services.code_interpreter import CodeInterpreter
    workspace = request.app.state.settings.storage_dir / "users" / user.id / "sandbox"
    return CodeInterpreter(workspace=str(workspace))


class CodeExecuteRequest(BaseModel):
    code: str
    language: str = "python"
    timeout: int = 30


@router.post("/execute")
async def execute_code(req: CodeExecuteRequest, request: Request, user: User = Depends(get_current_user)):
    try:
        interp = _get_interp(request, user)
        timeout = min(req.timeout, 60)
        result = await interp.execute(req.code, req.language, timeout)
        log.info("Code executed: user=%s lang=%s status=%s", user.id, req.language, result.get("status"))
        return result
    except Exception as e:
        log.error("Code execution failed: %s", e, exc_info=True)
        raise


@router.get("/history")
def code_history(limit: int = 20, request: Request = None, user: User = Depends(get_current_user)):
    return {"history": _get_interp(request, user).get_history(limit)}


@router.delete("/history")
def clear_history(request: Request = None, user: User = Depends(get_current_user)):
    _get_interp(request, user).clear_history()
    return {"status": "cleared"}
