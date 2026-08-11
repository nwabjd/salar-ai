import asyncio
import json
import logging
from typing import Optional, Tuple

import anyio
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import AgentRun, AuditEvent, Conversation, Document, Memory, Message, User, token_id
from ..schemas import ChatRequest, ChatResponse, ConversationCreate, ConversationDetail, ConversationResponse
from ..security import get_current_user
from ..services.agents import PreparedAgentContext
from ..services.agents.policy import RESOURCEFUL_RESPONSE_POLICY
from ..services.agents.run_store import AgentRunStore
from .agent import TOOL_DEFINITIONS, execute_tool
from .deps import check_quota

log = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

MAX_AGENT_ROUNDS = 5


class DisconnectAwareStreamingResponse(StreamingResponse):
    def __init__(self, content, *, on_disconnect, **kwargs):
        super().__init__(content, **kwargs)
        self.on_disconnect = on_disconnect

    async def _notify_disconnect(self) -> None:
        try:
            await self.on_disconnect()
        except Exception as error:
            log.error("Disconnect handling failed: %s", type(error).__name__)

    async def listen_for_disconnect(self, receive) -> None:
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                await self._notify_disconnect()
                break

    async def __call__(self, scope, receive, send) -> None:
        # Own both sides of the ASGI lifecycle so disconnect reconciliation is
        # stable across Starlette versions. Newer versions use send failures
        # for ASGI 2.4+, while older versions only listen for http.disconnect.
        async with anyio.create_task_group() as task_group:
            async def stream_response() -> None:
                try:
                    await self.stream_response(send)
                except OSError:
                    await self._notify_disconnect()
                finally:
                    task_group.cancel_scope.cancel()

            async def watch_disconnect() -> None:
                try:
                    await self.listen_for_disconnect(receive)
                finally:
                    task_group.cancel_scope.cancel()

            task_group.start_soon(stream_response)
            task_group.start_soon(watch_disconnect)

        if self.background is not None:
            await self.background()


def _stage_agent_chat_outcome(db: Session, run_id: Optional[str], status: str, reason: str) -> None:
    if run_id is None:
        return
    run = db.get(AgentRun, run_id)
    if run is None:
        return
    previous_status = run.status
    store = AgentRunStore(db)
    store.step(
        run,
        "chat",
        status,
        detail={
            "status": status,
            "reason": reason,
            "previous_status": previous_status,
        },
        attempt=1,
    )
    store.finalize(run, status, error=reason if status in {"failed", "cancelled"} else "")


def _terminal_detail(
    *,
    conversation_id: str,
    status: str,
    reason: str,
    agent_run_id: Optional[str],
    detail: Optional[dict],
) -> dict:
    result = {
        "conversation_id": conversation_id,
        "status": status,
        "reason": reason,
        **(detail or {}),
    }
    if agent_run_id is not None:
        result["agent_run_id"] = agent_run_id
    return result


def _stage_chat_terminal_claim(
    db: Session,
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
    create_missing_run: bool = False,
) -> Tuple[str, bool]:
    existing = db.get(AuditEvent, terminal_event_id)
    if existing is not None:
        return existing.action, False

    db.add(AuditEvent(
        id=terminal_event_id,
        user_id=user_id,
        action=action,
        detail_json=json.dumps(_terminal_detail(
            conversation_id=conversation_id,
            status=status,
            reason=reason,
            agent_run_id=agent_run_id,
            detail=detail,
        )),
    ))
    # The primary-key insert is the durable terminal claim. It must be flushed
    # before the run is changed so a losing contender cannot overwrite it.
    db.flush()
    if create_missing_run and agent_run_id is not None and db.get(AgentRun, agent_run_id) is None:
        db.add(AgentRun(
            id=agent_run_id,
            user_id=user_id,
            conversation_id=conversation_id,
            kind="research",
            status="running",
            input_json=json.dumps({"query": prompt}),
        ))
        db.flush()
    _stage_agent_chat_outcome(db, agent_run_id, status, reason)
    return action, True


def _load_terminal_action(session_factory, terminal_event_id: str) -> Optional[str]:
    check_db = None
    try:
        check_db = session_factory()
        event = check_db.get(AuditEvent, terminal_event_id)
        return event.action if event is not None else None
    except Exception as error:
        log.error("Unable to inspect terminal outcome: %s", type(error).__name__)
        return None
    finally:
        if check_db is not None:
            try:
                check_db.close()
            except Exception:
                pass


def _load_message(session_factory, message_id: str) -> Optional[Message]:
    check_db = None
    try:
        check_db = session_factory()
        return check_db.get(Message, message_id)
    except Exception as error:
        log.error("Unable to inspect chat message: %s", type(error).__name__)
        return None
    finally:
        if check_db is not None:
            try:
                check_db.close()
            except Exception:
                pass


def _agent_run_exists(session_factory, run_id: Optional[str]) -> bool:
    if run_id is None:
        return False
    check_db = None
    try:
        check_db = session_factory()
        return check_db.get(AgentRun, run_id) is not None
    except Exception as error:
        log.error("Unable to inspect agent run: %s", type(error).__name__)
        return False
    finally:
        if check_db is not None:
            try:
                check_db.close()
            except Exception:
                pass


def _load_committed_chat_response(
    session_factory,
    terminal_event_id: str,
    user_message_id: str,
    assistant_message_id: str,
) -> Optional[ChatResponse]:
    check_db = None
    try:
        check_db = session_factory()
        event = check_db.get(AuditEvent, terminal_event_id)
        if event is None or event.action != "chat.completed":
            return None
        user_message = check_db.get(Message, user_message_id)
        assistant_message = check_db.get(Message, assistant_message_id)
        if user_message is None or assistant_message is None:
            return None
        return ChatResponse(user_message=user_message, assistant_message=assistant_message)
    except Exception as error:
        log.error("Unable to reload committed chat response: %s", type(error).__name__)
        return None
    finally:
        if check_db is not None:
            try:
                check_db.close()
            except Exception:
                pass


def _load_stream_done_event(session_factory, terminal_event_id: str) -> Optional[str]:
    check_db = None
    try:
        check_db = session_factory()
        event = check_db.get(AuditEvent, terminal_event_id)
        if event is None or event.action != "chat.completed":
            return None
        detail = json.loads(event.detail_json)
        message_id = detail.get("message_id")
        created_at = detail.get("created_at")
        if not message_id or not created_at:
            return None
        return f"data: {json.dumps({'type': 'done', 'message_id': message_id, 'created_at': created_at})}\n\n"
    except Exception as error:
        log.error("Unable to reload committed stream result: %s", type(error).__name__)
        return None
    finally:
        if check_db is not None:
            try:
                check_db.close()
            except Exception:
                pass


def _reconcile_chat_terminal(
    session_factory,
    *,
    terminal_event_id: str,
    user_id: str,
    conversation_id: str,
    prompt: str,
    action: str,
    status: str,
    reason: str,
    agent_run_id: Optional[str] = None,
    detail: dict = None,
) -> Optional[str]:
    audit_db = None
    try:
        audit_db = session_factory()
        observed_action, claimed = _stage_chat_terminal_claim(
            audit_db,
            terminal_event_id=terminal_event_id,
            user_id=user_id,
            conversation_id=conversation_id,
            prompt=prompt,
            action=action,
            status=status,
            reason=reason,
            agent_run_id=agent_run_id,
            detail=detail,
            create_missing_run=True,
        )
        if not claimed:
            return observed_action
        audit_db.commit()
        return action
    except IntegrityError:
        if audit_db is not None:
            try:
                audit_db.rollback()
            except Exception:
                pass
        return _load_terminal_action(session_factory, terminal_event_id)
    except Exception as audit_error:
        if audit_db is not None:
            try:
                audit_db.rollback()
            except Exception:
                pass
        observed_action = _load_terminal_action(session_factory, terminal_event_id)
        if observed_action is not None:
            return observed_action
        log.error("Unable to persist %s outcome: %s", action, type(audit_error).__name__)
        return None
    finally:
        if audit_db is not None:
            try:
                audit_db.close()
            except Exception:
                pass


def _persist_stream_terminal_audit(
    session_factory,
    *,
    user_id: str,
    conversation_id: str,
    action: str,
    agent_run_id: Optional[str] = None,
    terminal_event_id: Optional[str] = None,
    detail: dict,
) -> Optional[str]:
    status = detail.get("status", "failed")
    return _reconcile_chat_terminal(
        session_factory,
        terminal_event_id=terminal_event_id or token_id(),
        user_id=user_id,
        conversation_id=conversation_id,
        prompt="",
        action=action,
        status=status,
        reason=detail.get("reason") or detail.get("error_message") or "Stream ended.",
        agent_run_id=agent_run_id,
        detail=detail,
    )


def owned_conversation(db: Session, user_id: str, conversation_id: str) -> Conversation:
    conversation = db.scalar(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.post("/api/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conversation = Conversation(user_id=user.id, title=payload.title.strip() or "New conversation", project_id=payload.project_id)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("/api/conversations", response_model=list[ConversationResponse])
def list_conversations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return list(
        db.scalars(select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.updated_at.desc()))
    )


@router.get("/api/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return owned_conversation(db, user.id, conversation_id)


@router.post("/api/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    quota: dict = Depends(check_quota),
):
    conversation = owned_conversation(db, user.id, payload.conversation_id)
    prompt = payload.content.strip()
    if not prompt:
        raise HTTPException(status_code=422, detail="Message cannot be empty")
    history = list(conversation.messages)
    memories = list(db.scalars(select(Memory).where(Memory.user_id == user.id).order_by(Memory.updated_at.desc()).limit(12)))
    documents = list(db.scalars(select(Document).where(Document.user_id == user.id).order_by(Document.created_at.desc()).limit(6)))
    prepared = await request.app.state.agent_orchestrator.prepare(
        prompt,
        db,
        user.id,
        conversation.id,
        commit=False,
    )
    response_text = await request.app.state.coordinator.reply(
        prompt=prompt,
        messages=history,
        memories=memories,
        documents=documents,
        agent_context=prepared.context,
    )
    terminal_event_id = token_id()
    user_message = Message(id=token_id(), conversation_id=conversation.id, role="user", content=prompt)
    assistant_message = Message(id=token_id(), conversation_id=conversation.id, role="assistant", content=response_text)
    db.add_all([user_message, assistant_message])
    db.flush()
    _stage_chat_terminal_claim(
        db,
        terminal_event_id=terminal_event_id,
        user_id=user.id,
        conversation_id=conversation.id,
        prompt=prompt,
        action="chat.completed",
        status="completed",
        reason="Chat response persisted successfully.",
        agent_run_id=prepared.run_id,
    )
    db.refresh(user_message)
    db.refresh(assistant_message)
    response = ChatResponse(user_message=user_message, assistant_message=assistant_message)
    try:
        db.commit()
    except Exception as error:
        db.rollback()
        committed = _load_committed_chat_response(
            request.app.state.SessionLocal,
            terminal_event_id,
            user_message.id,
            assistant_message.id,
        )
        if committed is not None:
            return committed
        outcome = _reconcile_chat_terminal(
            request.app.state.SessionLocal,
            terminal_event_id=terminal_event_id,
            user_id=user.id,
            conversation_id=conversation.id,
            prompt=prompt,
            action="chat.failed",
            status="failed",
            reason="Chat transaction failed.",
            agent_run_id=prepared.run_id,
            detail={"error_class": type(error).__name__[:120]},
        )
        if outcome == "chat.completed":
            committed = _load_committed_chat_response(
                request.app.state.SessionLocal,
                terminal_event_id,
                user_message.id,
                assistant_message.id,
            )
            if committed is not None:
                return committed
        raise
    return response


@router.post("/api/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    quota: dict = Depends(check_quota),
):
    conversation = owned_conversation(db, user.id, payload.conversation_id)
    prompt = payload.content.strip()
    if not prompt:
        raise HTTPException(status_code=422, detail="Message cannot be empty")
    fast = getattr(payload, "fast", False)
    history = list(conversation.messages)
    terminal_event_id = token_id()
    user_message_id = token_id()
    assistant_message_id = token_id()
    prepared = PreparedAgentContext(agent_kind="none", context="")
    try:
        if not fast:
            memories = list(db.scalars(select(Memory).where(Memory.user_id == user.id).order_by(Memory.updated_at.desc()).limit(12)))
            documents = list(db.scalars(select(Document).where(Document.user_id == user.id).order_by(Document.created_at.desc()).limit(6)))
            prepared = await request.app.state.agent_orchestrator.prepare(
                prompt,
                db,
                user.id,
                conversation.id,
                commit=False,
            )

        user_message = Message(
            id=user_message_id,
            conversation_id=conversation.id,
            role="user",
            content=prompt,
        )
        db.add(user_message)
        db.commit()
    except asyncio.CancelledError:
        db.rollback()
        setup_persisted = _load_message(request.app.state.SessionLocal, user_message_id) is not None
        run_persisted = _agent_run_exists(request.app.state.SessionLocal, prepared.run_id)
        if setup_persisted or run_persisted:
            _reconcile_chat_terminal(
                request.app.state.SessionLocal,
                terminal_event_id=terminal_event_id,
                user_id=user.id,
                conversation_id=conversation.id,
                prompt=prompt,
                action="chat.cancelled",
                status="cancelled",
                reason="Stream setup was cancelled.",
                agent_run_id=prepared.run_id,
            )
        raise
    except Exception:
        db.rollback()
        setup_persisted = _load_message(request.app.state.SessionLocal, user_message_id) is not None
        if not setup_persisted:
            if _agent_run_exists(request.app.state.SessionLocal, prepared.run_id):
                _reconcile_chat_terminal(
                    request.app.state.SessionLocal,
                    terminal_event_id=terminal_event_id,
                    user_id=user.id,
                    conversation_id=conversation.id,
                    prompt=prompt,
                    action="chat.failed",
                    status="failed",
                    reason="Stream setup failed.",
                    agent_run_id=prepared.run_id,
                )
            raise

    coordinator = request.app.state.coordinator
    gemini = coordinator.gemini

    async def generate():
        full_response = []

        if fast:
            agent_system = (
                "You are SALAR, a helpful voice assistant. "
                "Respond to exactly what the user asked. "
                "Be conversational and natural, like a knowledgeable friend. "
                "Give complete answers — don't cut responses short. "
                "If the question needs a detailed answer, give it. "
                "If it's a simple question, keep it brief. "
                "No bullet points, no markdown, no formatting — just plain spoken English. "
                "After using a tool, tell the user the full result naturally."
                f"\n\n{RESOURCEFUL_RESPONSE_POLICY}"
            )
            recent_history = history[-6:] if len(history) > 6 else history
            messages = [{"role": "system", "content": agent_system}]
            messages.extend({"role": m.role, "content": m.content} for m in recent_history)
            messages.append({"role": "user", "content": prompt})
        else:
            messages = coordinator.build_payload(
                prompt=prompt,
                messages=history,
                memories=memories,
                documents=documents,
                agent_context=prepared.context,
            )
            messages[0]["content"] += (
                "\n\nUse available tools when the user asks you to do something on their computer. "
                "Always be helpful, concise, and confirm actions. "
                "CRITICAL: After ANY tool call, you MUST reply with a natural-language message to the user summarizing the result. "
                "Never leave the user without a spoken response. If a tool returns a time, temperature, file list, etc., tell the user what it said in plain English."
            )

        max_rounds = 2 if fast else MAX_AGENT_ROUNDS
        tools_used = []
        save_db = request.app.state.SessionLocal()
        try:
            for agent_round in range(max_rounds):
                result = await gemini.chat_with_tools(messages, TOOL_DEFINITIONS)

                if result["function_calls"]:
                    for fc in result["function_calls"]:
                        tool_name = fc.get("name", "")
                        tool_args = fc.get("args", {})
                        log.info("Agent tool: %s(%s)", tool_name, json.dumps(tool_args)[:200])

                        yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_name, 'args': tool_args})}\n\n"

                        tool_result = await execute_tool(tool_name, tool_args, user.id, save_db, is_admin=user.is_admin)
                        tools_used.append({"tool": tool_name, "args": tool_args, "result": tool_result})

                        yield f"data: {json.dumps({'type': 'tool_result', 'tool': tool_name, 'result': tool_result})}\n\n"

                        messages.append({"role": "model", "content": [{"functionCall": fc}]})
                        messages.append({"role": "user", "content": [{"functionResponse": {"name": tool_name, "response": tool_result}}]})

                    text_with_calls = result.get("text", "")
                    if text_with_calls:
                        full_response.append(text_with_calls)
                        yield f"data: {json.dumps({'type': 'token', 'content': text_with_calls})}\n\n"
                    continue

                response_text = result.get("text", "")
                if response_text:
                    full_response.append(response_text)
                    yield f"data: {json.dumps({'type': 'token', 'content': response_text})}\n\n"
                break

            if not full_response:
                if tools_used:
                    last_result = tools_used[-1].get("result", {})
                    detail = last_result.get("stdout", "") or last_result.get("detail", "") or str(last_result)
                    fallback = f"Done. Here's what I found:\n{detail.strip()}"
                else:
                    fallback = "I completed the requested tasks. Please check the results above."
                full_response.append(fallback)
                yield f"data: {json.dumps({'type': 'token', 'content': fallback})}\n\n"

            response_text = "".join(full_response)
            assistant_msg = Message(
                id=assistant_message_id,
                conversation_id=conversation.id,
                role="assistant",
                content=response_text,
            )
            save_db.add(assistant_msg)
            save_db.flush()
            save_db.refresh(assistant_msg)
            done_payload = {
                "type": "done",
                "message_id": assistant_msg.id,
                "created_at": str(assistant_msg.created_at),
            }
            done_event = f"data: {json.dumps(done_payload)}\n\n"
            observed_action, claimed = _stage_chat_terminal_claim(
                save_db,
                terminal_event_id=terminal_event_id,
                user_id=user.id,
                conversation_id=conversation.id,
                prompt=prompt,
                action="chat.completed",
                status="completed",
                reason="Stream response persisted successfully.",
                agent_run_id=prepared.run_id,
                detail={
                    "tools": [t["tool"] for t in tools_used],
                    "message_id": assistant_msg.id,
                    "created_at": str(assistant_msg.created_at),
                },
            )
            if not claimed:
                save_db.rollback()
                if observed_action == "chat.completed":
                    persisted_done = _load_stream_done_event(
                        request.app.state.SessionLocal,
                        terminal_event_id,
                    )
                    if persisted_done is not None:
                        yield persisted_done
                return
            try:
                save_db.commit()
            except Exception:
                save_db.rollback()
                if _load_terminal_action(request.app.state.SessionLocal, terminal_event_id) == "chat.completed":
                    yield done_event
                    return
                raise
            yield done_event
        except asyncio.CancelledError:
            save_db.rollback()
            _reconcile_chat_terminal(
                request.app.state.SessionLocal,
                terminal_event_id=terminal_event_id,
                user_id=user.id,
                conversation_id=conversation.id,
                prompt=prompt,
                action="chat.cancelled",
                status="cancelled",
                reason="Stream cancelled before completion.",
                agent_run_id=prepared.run_id,
            )
            raise
        except Exception as e:
            save_db.rollback()
            observed_action = _reconcile_chat_terminal(
                request.app.state.SessionLocal,
                terminal_event_id=terminal_event_id,
                user_id=user.id,
                conversation_id=conversation.id,
                prompt=prompt,
                action="chat.failed",
                status="failed",
                reason="Stream processing failed.",
                agent_run_id=prepared.run_id,
                detail={
                    "error_class": type(e).__name__[:120],
                    "error_message": "Stream processing failed.",
                },
            )
            if observed_action == "chat.completed":
                persisted_done = _load_stream_done_event(
                    request.app.state.SessionLocal,
                    terminal_event_id,
                )
                if persisted_done is not None:
                    yield persisted_done
                return
            if observed_action == "chat.cancelled":
                return
            log.error("Agent stream failed: %s", type(e).__name__)
            fallback = "The AI service is temporarily unavailable. Your message was saved — please try again."
            yield f"data: {json.dumps({'type': 'error', 'detail': fallback, 'error': fallback, 'code': 'stream_failed'})}\n\n"
        finally:
            save_db.close()

    async def on_disconnect() -> None:
        _reconcile_chat_terminal(
            request.app.state.SessionLocal,
            terminal_event_id=terminal_event_id,
            user_id=user.id,
            conversation_id=conversation.id,
            prompt=prompt,
            action="chat.cancelled",
            status="cancelled",
            reason="Client disconnected before stream completion.",
            agent_run_id=prepared.run_id,
        )

    return DisconnectAwareStreamingResponse(generate(), on_disconnect=on_disconnect, media_type="text/event-stream", headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "Content-Encoding": "identity",
    })
