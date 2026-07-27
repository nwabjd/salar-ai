"""Code interpreter endpoints — execute Python/JS snippets."""

import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from ..security import get_current_user
from ..models import User

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/code", tags=["code"])

_interpreter = None


def _get_interp():
    global _interpreter
    if _interpreter is None:
        from ..services.code_interpreter import CodeInterpreter
        _interpreter = CodeInterpreter()
    return _interpreter


class CodeExecuteRequest(BaseModel):
    code: str
    language: str = "python"
    timeout: int = 30


@router.post("/execute")
async def execute_code(req: CodeExecuteRequest, user: User = Depends(get_current_user)):
    try:
        interp = _get_interp()
        timeout = min(req.timeout, 60)
        result = await interp.execute(req.code, req.language, timeout)
        log.info("Code executed: lang=%s status=%s", req.language, result.get("status"))
        return result
    except Exception as e:
        log.error("Code execution failed: %s", e, exc_info=True)
        raise


@router.get("/history")
def code_history(limit: int = 20, user: User = Depends(get_current_user)):
    return {"history": _get_interp().get_history(limit)}


@router.delete("/history")
def clear_history(user: User = Depends(get_current_user)):
    _get_interp().clear_history()
    return {"status": "cleared"}
