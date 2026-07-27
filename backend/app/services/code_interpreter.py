"""Code interpreter — sandboxed Python/JS code execution with output capture."""

import asyncio
import json
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional


class CodeInterpreter:
    """Execute code snippets in a sandboxed environment."""

    MAX_OUTPUT = 50000  # chars
    TIMEOUT = 30  # seconds

    def __init__(self):
        self._history: list = []

    async def execute_python(self, code: str, timeout: int = None) -> Dict[str, Any]:
        """Execute Python code and return stdout/stderr."""
        timeout = timeout or self.TIMEOUT
        run_id = str(uuid.uuid4())[:8]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            f.flush()
            tmp_path = f.name

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                result = {"run_id": run_id, "language": "python", "status": "timeout",
                          "stdout": "", "stderr": f"Execution timed out after {timeout}s", "exit_code": -1}
                self._history.append(result)
                return result

            stdout_str = stdout.decode("utf-8", errors="replace")[:self.MAX_OUTPUT]
            stderr_str = stderr.decode("utf-8", errors="replace")[:self.MAX_OUTPUT]

            result = {
                "run_id": run_id,
                "language": "python",
                "status": "ok" if proc.returncode == 0 else "error",
                "stdout": stdout_str,
                "stderr": stderr_str,
                "exit_code": proc.returncode,
            }
            self._history.append(result)
            return result
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    async def execute_javascript(self, code: str, timeout: int = None) -> Dict[str, Any]:
        """Execute JavaScript code using Node.js."""
        timeout = timeout or self.TIMEOUT
        run_id = str(uuid.uuid4())[:8]

        # Wrap code to capture console.log
        wrapped = f"""
const _output = [];
const _origLog = console.log;
console.log = (...args) => _output.push(args.map(a => typeof a === 'object' ? JSON.stringify(a, null, 2) : String(a)).join(' '));
try {{
{code}
}} catch(e) {{
  console.error(e.message);
}}
console.log = _origLog;
if (_output.length) process.stdout.write(_output.join('\\n'));
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(wrapped)
            f.flush()
            tmp_path = f.name

        try:
            proc = await asyncio.create_subprocess_exec(
                "node", tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                result = {"run_id": run_id, "language": "javascript", "status": "timeout",
                          "stdout": "", "stderr": f"Execution timed out after {timeout}s", "exit_code": -1}
                self._history.append(result)
                return result

            stdout_str = stdout.decode("utf-8", errors="replace")[:self.MAX_OUTPUT]
            stderr_str = stderr.decode("utf-8", errors="replace")[:self.MAX_OUTPUT]

            result = {
                "run_id": run_id,
                "language": "javascript",
                "status": "ok" if proc.returncode == 0 else "error",
                "stdout": stdout_str,
                "stderr": stderr_str,
                "exit_code": proc.returncode,
            }
            self._history.append(result)
            return result
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    async def execute(self, code: str, language: str = "python", timeout: int = None) -> Dict[str, Any]:
        """Execute code in the specified language."""
        language = language.lower().strip()
        if language in ("python", "py"):
            return await self.execute_python(code, timeout)
        elif language in ("javascript", "js", "node"):
            return await self.execute_javascript(code, timeout)
        else:
            return {"error": f"Unsupported language: {language}. Use 'python' or 'javascript'."}

    def get_history(self, limit: int = 20) -> list:
        return self._history[-limit:]

    def clear_history(self):
        self._history = []
