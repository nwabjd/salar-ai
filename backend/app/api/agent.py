import asyncio
import json
import logging
import re
from typing import Iterable, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditEvent, Conversation, Document, Memory, Message, User, token_id
from ..schemas import ChatRequest
from ..security import get_current_user
from ..services.agent import TOOL_DEFINITIONS, execute_tool
from ..services.agents import PreparedAgentContext
from ..services.agents.policy import RESOURCEFUL_RESPONSE_POLICY
from .chat import (
    _agent_run_exists,
    _load_terminal_action,
    _reconcile_chat_terminal,
    _situation_context,
    _stage_chat_terminal_claim,
)
from .deps import check_quota

log = logging.getLogger(__name__)
router = APIRouter(tags=["agent"])

MAX_TOOL_ROUNDS = 5
_FAILED_TOOL_STATUSES = {"error", "failed", "failure", "exception"}
_FAILED_TOOL_KEYS = {"error", "exception", "traceback", "stack", "stack_trace"}


def _build_agent_system_prompt(memories: Iterable, documents: Iterable, agent_context: str = "", situations_context: str = "") -> str:
    context_parts = []
    memory_text = "\n".join(f"- {item.title}: {item.content}" for item in memories)
    if memory_text:
        context_parts.append(f"Relevant saved memory:\n{memory_text}")
    document_text = "\n".join(f"- {item.filename}: {(getattr(item, 'extracted_text', None) or '')[:800]}" for item in documents)
    if document_text:
        context_parts.append(f"Relevant documents:\n{document_text}")
    if situations_context:
        context_parts.append(
            "What is happening right now (from your world model):\n"
            f"{situations_context}\n"
            "If any of these matters to the user's task, mention it proactively — "
            "don't stay silent about a deadline, failing build, or collaborator signal."
        )
    if agent_context:
        context_parts.append(f"Prepared specialist context:\n{agent_context}")

    system = (
        "You are SALAR, an autonomous AI assistant with control over the user's PC and devices. "
        "You can open applications, run commands, manage files, browse the web, send notifications, "
        "and control connected devices.\n\n"
        "When the user asks you to do something on their computer or phone, use the available tools "
        "to execute the task. Always confirm what you did and report results.\n\n"
        "IMPORTANT: When a task requires multiple steps, break it down and execute tools one at a time. "
        "After each tool execution, you'll receive the result and can decide the next step.\n\n"
        "FILE CREATION: To create files inside a new folder, use write_file with the full relative path "
        "(e.g. 'Desktop/My Project/index.html'). write_file automatically creates any missing parent "
        "directories — you do NOT need to mkdir first. This avoids quoting issues with spaces in folder names.\n\n"
        "Default to creating files and folders on the Desktop unless the user specifies otherwise.\n\n"
        "Always be helpful, concise, and confirm actions before executing potentially destructive operations "
        "(like deleting files or running system commands)."
        f"\n\n{RESOURCEFUL_RESPONSE_POLICY}"
    )
    if context_parts:
        system += "\n\n" + "\n\n".join(context_parts)
    return system


def _safe_tool_name(tool_name: str) -> str:
    bounded = re.sub(r"[^A-Za-z0-9_.-]", "_", str(tool_name or ""))[:64]
    return bounded or "tool"


def _is_failed_tool_result(result) -> bool:
    if not isinstance(result, dict):
        return False
    status = str(result.get("status", "")).strip().lower()
    if status in _FAILED_TOOL_STATUSES or result.get("success") is False:
        return True
    return any(result.get(key) not in (None, "", False, [], {}) for key in _FAILED_TOOL_KEYS)


def _sanitize_tool_exchange(tool_name: str, tool_args, result):
    if not _is_failed_tool_result(result):
        return tool_name, tool_args, result
    safe_name = _safe_tool_name(tool_name)
    return safe_name, {}, {
        "status": "error",
        "code": "tool_execution_failed",
        "tool": safe_name,
        "detail": "The tool could not complete safely.",
    }


def _load_committed_agent_response(
    session_factory,
    terminal_event_id: str,
    expected_action: str,
    user_message_id: str,
    assistant_message_id: str,
    tools_used: list,
) -> Optional[dict]:
    check_db = None
    try:
        check_db = session_factory()
        event = check_db.get(AuditEvent, terminal_event_id)
        if event is None or event.action != expected_action:
            return None
        user_message = check_db.get(Message, user_message_id)
        assistant_message = check_db.get(Message, assistant_message_id)
        if user_message is None or assistant_message is None:
            return None
        return {
            "user_message": {
                "id": user_message.id,
                "role": "user",
                "content": user_message.content,
                "created_at": str(user_message.created_at),
            },
            "assistant_message": {
                "id": assistant_message.id,
                "role": "assistant",
                "content": assistant_message.content,
                "created_at": str(assistant_message.created_at),
            },
            "tools_used": tools_used,
        }
    except Exception as error:
        log.error("Unable to reload committed agent response: %s", type(error).__name__)
        return None
    finally:
        if check_db is not None:
            try:
                check_db.close()
            except Exception:
                pass


def _resolve_prepared_run_id(
    session_factory,
    prepared: PreparedAgentContext,
    preparation_run_id: str,
) -> Optional[str]:
    if prepared.run_id is not None:
        return prepared.run_id
    return preparation_run_id if _agent_run_exists(session_factory, preparation_run_id) else None


def _commit_agent_terminal(
    db: Session,
    session_factory,
    *,
    terminal_event_id: str,
    user_id: str,
    conversation_id: str,
    prompt: str,
    action: str,
    status: str,
    reason: str,
    agent_run_id: Optional[str],
    detail: Optional[dict] = None,
    reconcile_if_absent: bool = False,
) -> Optional[str]:
    try:
        observed_action, claimed = _stage_chat_terminal_claim(
            db,
            terminal_event_id=terminal_event_id,
            user_id=user_id,
            conversation_id=conversation_id,
            prompt=prompt,
            action=action,
            status=status,
            reason=reason,
            agent_run_id=agent_run_id,
            detail=detail,
            outcome_name="agent",
            create_missing_run=reconcile_if_absent,
        )
        if not claimed:
            db.rollback()
            return observed_action
        try:
            db.commit()
            return action
        except (Exception, asyncio.CancelledError):
            db.rollback()
            observed_action = _load_terminal_action(session_factory, terminal_event_id)
            if observed_action is not None:
                return observed_action
    except (Exception, asyncio.CancelledError):
        db.rollback()
        observed_action = _load_terminal_action(session_factory, terminal_event_id)
        if observed_action is not None:
            return observed_action

    if not reconcile_if_absent:
        return None
    return _reconcile_chat_terminal(
        session_factory,
        terminal_event_id=terminal_event_id,
        user_id=user_id,
        conversation_id=conversation_id,
        prompt=prompt,
        action=action,
        status=status,
        reason=reason,
        agent_run_id=agent_run_id,
        detail=detail,
        outcome_name="agent",
    )


@router.post("/api/agent")
async def agent_chat(
    payload: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    quota: dict = Depends(check_quota),
):
    conversation = db.scalar(
        select(Conversation)
        .where(Conversation.id == payload.conversation_id, Conversation.user_id == user.id)
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    prompt = payload.content.strip()
    if not prompt:
        raise HTTPException(status_code=422, detail="Message cannot be empty")

    history = list(conversation.messages)
    memories = list(db.scalars(
        select(Memory).where(Memory.user_id == user.id)
        .order_by(Memory.updated_at.desc()).limit(12)
    ))
    documents = list(db.scalars(
        select(Document).where(Document.user_id == user.id)
        .order_by(Document.created_at.desc()).limit(6)
    ))
    terminal_event_id = token_id()
    user_message_id = token_id()
    assistant_message_id = token_id()
    preparation_run_id = token_id()
    prepared = PreparedAgentContext(agent_kind="none", context="")
    tools_used = []
    tool_db = None
    preparation_db = None
    try:
        try:
            preparation_db = request.app.state.SessionLocal()
            prepared = await request.app.state.agent_orchestrator.prepare(
                prompt,
                preparation_db,
                user.id,
                conversation.id,
                commit=True,
                run_id=preparation_run_id,
            )
        finally:
            if preparation_db is not None:
                preparation_db.close()
                preparation_db = None

        gemini = request.app.state.coordinator.gemini
        system_prompt = _build_agent_system_prompt(memories, documents, prepared.context, _situation_context(db, user.id))
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend({"role": m.role, "content": m.content} for m in history[-12:])
        messages.append({"role": "user", "content": prompt})
        tool_db = request.app.state.SessionLocal()

        response_text = ""
        terminal_action = "agent.completed"
        terminal_status = "completed"
        terminal_reason = "Agent response persisted successfully."
        for round_num in range(MAX_TOOL_ROUNDS):
            result = await gemini.chat_with_tools(messages, TOOL_DEFINITIONS)

            if result["function_calls"]:
                for fc in result["function_calls"]:
                    tool_name = fc.get("name", "")
                    tool_args = fc.get("args", {})
                    log.info("Agent tool call: %s(%s)", tool_name, json.dumps(tool_args)[:200])

                    raw_tool_result = await execute_tool(
                        tool_name,
                        tool_args,
                        user.id,
                        tool_db,
                        is_admin=user.is_admin,
                        base_url=str(request.base_url),
                        jwt_secret=request.app.state.settings.jwt_secret,
                    )
                    try:
                        factory = getattr(request.app.state, "world_ingestor_factory", None)
                        if factory is not None:
                            ingestor = factory()
                            ingestor.ingest_tool(user.id, {"tool": tool_name, "args": tool_args, "result": raw_tool_result}, source="agent")
                            ingestor.graph.db.commit()
                    except Exception:
                        log.warning("world ingest failed for tool %s", tool_name, exc_info=True)
                    public_tool_name, public_tool_args, tool_result = _sanitize_tool_exchange(
                        tool_name,
                        tool_args,
                        raw_tool_result,
                    )
                    tools_used.append({
                        "tool": public_tool_name,
                        "args": public_tool_args,
                        "result": tool_result,
                    })

                    public_function_call = fc if public_tool_args is tool_args else {
                        "name": public_tool_name,
                        "args": public_tool_args,
                    }
                    messages.append({"role": "model", "content": [{"functionCall": public_function_call}]})
                    messages.append({
                        "role": "user",
                        "content": [{"functionResponse": {
                            "name": public_tool_name,
                            "response": tool_result,
                        }}],
                    })
                continue

            response_text = result.get("text", "")
            if response_text:
                break

        if not response_text:
            response_text = (
                "I reached the processing limit after executing the available tool steps. "
                "Please review the results and continue if needed."
            )
            terminal_action = "agent.partial"
            terminal_status = "partial"
            terminal_reason = "Agent reached the tool-processing limit before a final answer."

        with db.begin_nested():
            user_message = Message(
                id=user_message_id,
                conversation_id=conversation.id,
                role="user",
                content=prompt,
            )
            assistant_message = Message(
                id=assistant_message_id,
                conversation_id=conversation.id,
                role="assistant",
                content=response_text,
            )
            db.add_all([user_message, assistant_message])
            db.flush()
            db.refresh(user_message)
            db.refresh(assistant_message)
        observed_action = _commit_agent_terminal(
            db,
            request.app.state.SessionLocal,
            terminal_event_id=terminal_event_id,
            user_id=user.id,
            conversation_id=conversation.id,
            prompt=prompt,
            action=terminal_action,
            status=terminal_status,
            reason=terminal_reason,
            agent_run_id=prepared.run_id,
            detail={"tools": [item["tool"] for item in tools_used]},
        )
        if observed_action == terminal_action:
            committed = _load_committed_agent_response(
                request.app.state.SessionLocal,
                terminal_event_id,
                terminal_action,
                user_message_id,
                assistant_message_id,
                tools_used,
            )
            if committed is not None:
                return committed
        raise RuntimeError("Agent terminal outcome was not persisted.")
    except asyncio.CancelledError:
        agent_run_id = _resolve_prepared_run_id(
            request.app.state.SessionLocal,
            prepared,
            preparation_run_id,
        )
        _commit_agent_terminal(
            db,
            request.app.state.SessionLocal,
            terminal_event_id=terminal_event_id,
            user_id=user.id,
            conversation_id=conversation.id,
            prompt=prompt,
            action="agent.cancelled",
            status="cancelled",
            reason="Agent processing was cancelled.",
            agent_run_id=agent_run_id,
            detail={"tools": [item["tool"] for item in tools_used]},
            reconcile_if_absent=True,
        )
        raise
    except Exception as error:
        agent_run_id = _resolve_prepared_run_id(
            request.app.state.SessionLocal,
            prepared,
            preparation_run_id,
        )
        observed_action = _commit_agent_terminal(
            db,
            request.app.state.SessionLocal,
            terminal_event_id=terminal_event_id,
            user_id=user.id,
            conversation_id=conversation.id,
            prompt=prompt,
            action="agent.failed",
            status="failed",
            reason="Agent processing failed.",
            agent_run_id=agent_run_id,
            detail={
                "tools": [item["tool"] for item in tools_used],
                "error_class": type(error).__name__[:120],
                "error_message": "Agent processing failed.",
            },
            reconcile_if_absent=True,
        )
        if observed_action in {"agent.completed", "agent.partial"}:
            committed = _load_committed_agent_response(
                request.app.state.SessionLocal,
                terminal_event_id,
                observed_action,
                user_message_id,
                assistant_message_id,
                tools_used,
            )
            if committed is not None:
                return committed
        log.error("Agent request failed: %s", type(error).__name__)
        raise RuntimeError("Agent processing failed.") from None
    finally:
        if tool_db is not None:
            tool_db.close()
