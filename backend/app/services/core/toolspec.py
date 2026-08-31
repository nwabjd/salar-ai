# backend/app/services/core/toolspec.py
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

RISK_CATEGORY = {0: "read_only", 1: "safe", 2: "reversible", 3: "sensitive", 4: "destructive"}


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str = ""
    risk_level: int = 2
    permission_category: str = "reversible"
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    verification: str = "auto"
    undo: Optional[str] = None
    cost_class: str = "cheap"

    @property
    def requires_approval(self) -> bool:
        return self.risk_level >= 3


def _fs_spec(name: str, desc: str, risk: int) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=desc,
        risk_level=risk,
        permission_category=RISK_CATEGORY[risk],
        verification="auto",
        undo=None,
        cost_class="cheap",
    )


DEFAULT_SPECS: Dict[str, ToolSpec] = {
    "file_write": ToolSpec(
        name="file_write",
        description="Writes content to a file.",
        risk_level=2,
        permission_category="reversible",
        verification="file_write",
        cost_class="cheap",
    ),
    "file_read": ToolSpec(
        name="file_read",
        description="Reads a file.",
        risk_level=0,
        permission_category="read_only",
        verification="file_read",
        cost_class="free",
    ),
    "list_files": ToolSpec(
        name="list_files",
        description="Lists files in a directory.",
        risk_level=0,
        permission_category="read_only",
        verification="list_files",
        cost_class="free",
    ),
    "run_command": ToolSpec(
        name="run_command",
        description="Runs a shell command.",
        risk_level=2,
        permission_category="reversible",
        verification="run_command",
        cost_class="cheap",
    ),
    "code_run": ToolSpec(
        name="code_run",
        description="Executes a code snippet.",
        risk_level=3,
        permission_category="sensitive",
        verification="code_run",
        cost_class="cheap",
    ),
    "delete_file": ToolSpec(
        name="delete_file",
        description="Deletes a file or folder permanently. Cannot be undone.",
        risk_level=4,
        permission_category="destructive",
        verification="delete_file",
        cost_class="cheap",
    ),
    "open_url": ToolSpec(
        name="open_url",
        description="Fetches a web page.",
        risk_level=1,
        permission_category="safe",
        verification="open_url",
        cost_class="cheap",
    ),
    "browse_page": ToolSpec(
        name="browse_page",
        description="Browses and summarizes a web page.",
        risk_level=1,
        permission_category="safe",
        verification="auto",
        cost_class="cheap",
    ),
    "search_knowledge": ToolSpec(
        name="search_knowledge",
        description="Searches local memory.",
        risk_level=0,
        permission_category="read_only",
        verification="auto",
        cost_class="free",
    ),
    "search_documents": ToolSpec(
        name="search_documents",
        description="Searches user documents.",
        risk_level=0,
        permission_category="read_only",
        verification="auto",
        cost_class="free",
    ),
    "send_message": ToolSpec(
        name="send_message",
        description="Sends a message.",
        risk_level=1,
        permission_category="safe",
        verification="send_message",
        cost_class="cheap",
    ),
    "notify": ToolSpec(
        name="notify",
        description="Sends a notification.",
        risk_level=1,
        permission_category="safe",
        verification="send_message",
        cost_class="cheap",
    ),
    "screenshot": ToolSpec(
        name="screenshot",
        description="Captures the screen.",
        risk_level=2,
        permission_category="reversible",
        verification="auto",
        cost_class="cheap",
    ),
}


class ToolRegistry:
    def __init__(self, specs: Optional[Dict[str, ToolSpec]] = None) -> None:
        self._specs = dict(DEFAULT_SPECS)
        if specs:
            self._specs.update(specs)

    def spec(self, name: str) -> ToolSpec:
        return self._specs.get(
            name,
            ToolSpec(name=name, description="", risk_level=2, permission_category="reversible", verification="auto", cost_class="cheap"),
        )

    def specs(self) -> Dict[str, ToolSpec]:
        return dict(self._specs)

    def requires_approval(self, name: str) -> bool:
        return self.spec(name).requires_approval

    async def run(self, name: str, args: Dict[str, Any], user_id: str, db_session=None, is_admin: bool = False) -> Dict[str, Any]:
        from ..agent import execute_tool

        return await execute_tool(name, args, user_id, db_session=db_session, is_admin=is_admin)
