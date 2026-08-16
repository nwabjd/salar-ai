# backend/app/services/core/verification.py
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class VerifierResult:
    passed: bool
    confidence: float
    evidence: str
    verifier: str


class VerificationEngine:
    def __init__(self) -> None:
        self._verifiers: Dict[str, Callable[..., VerifierResult]] = {}
        self._register_builtins()

    def register(self, name: str, fn: Callable[..., VerifierResult]) -> None:
        self._verifiers[name] = fn

    async def verify(self, spec, args: Dict[str, Any], result: Any, ctx: Optional[Dict[str, Any]] = None) -> VerifierResult:
        verifier = getattr(spec, "verification", "auto") or "auto"
        fn = self._verifiers.get(verifier)
        if fn is None:
            return VerifierResult(False, 0.3, f"verifier '{verifier}' not registered", verifier)
        return fn(spec, args or {}, result, ctx or {})

    def _register_builtins(self) -> None:
        self.register("file_write", self._v_file_write)
        self.register("file_read", self._v_file_read)
        self.register("list_files", self._v_list_files)
        self.register("run_command", self._v_run_command)
        self.register("code_run", self._v_code_run)
        self.register("open_url", self._v_open_url)
        self.register("send_message", self._v_send_message)
        self.register("auto", self._v_auto)
        self.register("none", self._v_none)

    def _find_path(self, args: Dict[str, Any], result: Any) -> Optional[Path]:
        if isinstance(result, dict):
            for key in ("path", "filepath", "file_path", "name"):
                if result.get(key):
                    return Path(str(result[key]))
        for key in ("path", "filepath", "file_path"):
            if args.get(key):
                return Path(str(args[key]))
        return None

    def _v_file_write(self, spec, args, result, ctx) -> VerifierResult:
        path = self._find_path(args, result)
        if path is None:
            return VerifierResult(False, 0.3, "no path in result or args", "file_write")
        if not path.exists():
            return VerifierResult(False, 0.2, f"file does not exist: {path}", "file_write")
        expected = args.get("content") or args.get("text") or ctx.get("expected_content")
        if expected is not None:
            try:
                actual = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                return VerifierResult(False, 0.4, f"could not read back {path}", "file_write")
            if actual == str(expected):
                return VerifierResult(True, 0.99, f"read back {path}; content matches", "file_write")
            return VerifierResult(False, 0.5, f"content mismatch at {path}", "file_write")
        return VerifierResult(True, 0.9, f"file exists: {path}", "file_write")

    def _v_file_read(self, spec, args, result, ctx) -> VerifierResult:
        path = self._find_path(args, result)
        if path is None or not path.exists():
            return VerifierResult(False, 0.2, "file does not exist", "file_read")
        content = str(result.get("content", "")) if isinstance(result, dict) else str(result or "")
        if len(content) > 0:
            return VerifierResult(True, 0.97, f"read {len(content)} chars from {path}", "file_read")
        return VerifierResult(False, 0.5, "read returned empty content", "file_read")

    def _v_list_files(self, spec, args, result, ctx) -> VerifierResult:
        if isinstance(result, (list, tuple)) and len(result) >= 0:
            return VerifierResult(True, 0.9, f"list returned {len(result)} entries", "list_files")
        if isinstance(result, dict) and ("files" in result or "entries" in result):
            return VerifierResult(True, 0.9, "list returned files", "list_files")
        return VerifierResult(False, 0.4, "list result had an unexpected shape", "list_files")

    def _v_run_command(self, spec, args, result, ctx) -> VerifierResult:
        if isinstance(result, dict) and result.get("exit_code") == 0:
            return VerifierResult(True, 0.95, f"command exited 0: {args.get('command', '')[:80]}", "run_command")
        return VerifierResult(False, 0.2, f"command failed: {args.get('command', '')[:80]}", "run_command")

    def _v_code_run(self, spec, args, result, ctx) -> VerifierResult:
        if not isinstance(result, dict):
            return VerifierResult(False, 0.4, "code_run result not a dict", "code_run")
        if result.get("error") or result.get("error_message"):
            return VerifierResult(False, 0.2, f"code error: {result.get('error', result.get('error_message', ''))[:120]}", "code_run")
        if result.get("output") is not None or "result" in result:
            return VerifierResult(True, 0.93, "code executed without error", "code_run")
        return VerifierResult(False, 0.5, "code_run produced no output", "code_run")

    def _v_open_url(self, spec, args, result, ctx) -> VerifierResult:
        status = None
        if isinstance(result, dict):
            status = result.get("status_code") or result.get("status") or (result.get("response", {}) or {}).get("status_code")
        if status is not None and 200 <= int(status) <= 399:
            return VerifierResult(True, 0.96, f"HTTP {status}", "open_url")
        return VerifierResult(False, 0.3, f"unexpected HTTP status: {status}", "open_url")

    def _v_send_message(self, spec, args, result, ctx) -> VerifierResult:
        if isinstance(result, dict) and result.get("ok") is True:
            return VerifierResult(True, 0.9, "message send acknowledged", "send_message")
        return VerifierResult(False, 0.3, "send not acknowledged", "send_message")

    def _v_auto(self, spec, args, result, ctx) -> VerifierResult:
        if result is None:
            return VerifierResult(False, 0.3, "tool returned no result", "auto")
        if ctx.get("error"):
            return VerifierResult(False, 0.3, f"tool raised: {ctx['error']}", "auto")
        return VerifierResult(True, 0.8, "tool returned a non-empty result", "auto")

    def _v_none(self, spec, args, result, ctx) -> VerifierResult:
        return VerifierResult(True, 0.3, "no verifier configured", "none")
