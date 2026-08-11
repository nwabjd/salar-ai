import json
import logging
from typing import Iterable

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditEvent, Conversation, Document, Memory, Message, User
from ..schemas import ChatRequest
from ..security import get_current_user
from ..services.agent import TOOL_DEFINITIONS, execute_tool
from ..services.agents.policy import RESOURCEFUL_RESPONSE_POLICY
from .deps import check_quota

log = logging.getLogger(__name__)
router = APIRouter(tags=["agent"])

MAX_TOOL_ROUNDS = 5


def _build_agent_system_prompt(memories: Iterable, documents: Iterable, agent_context: str = "") -> str:
    context_parts = []
    memory_text = "\n".join(f"- {item.title}: {item.content}" for item in memories)
    if memory_text:
        context_parts.append(f"Relevant saved memory:\n{memory_text}")
    document_text = "\n".join(f"- {item.filename}: {(getattr(item, 'extracted_text', None) or '')[:800]}" for item in documents)
    if document_text:
        context_parts.append(f"Relevant documents:\n{document_text}")
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
        "Always be helpful, concise, and confirm actions before executing potentially destructive operations "
        "(like deleting files or running system commands)."
        f"\n\n{RESOURCEFUL_RESPONSE_POLICY}"
    )
    if context_parts:
        system += "\n\n" + "\n\n".join(context_parts)
    return system


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
    prepared = await request.app.state.agent_orchestrator.prepare(
        prompt,
        db,
        user.id,
        conversation.id,
    )

    gemini = request.app.state.coordinator.gemini
    system_prompt = _build_agent_system_prompt(memories, documents, prepared.context)

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend({"role": m.role, "content": m.content} for m in history[-12:])
    messages.append({"role": "user", "content": prompt})

    tools_used = []
    for round_num in range(MAX_TOOL_ROUNDS):
        result = await gemini.chat_with_tools(messages, TOOL_DEFINITIONS)

        if result["function_calls"]:
            for fc in result["function_calls"]:
                tool_name = fc.get("name", "")
                tool_args = fc.get("args", {})
                log.info("Agent tool call: %s(%s)", tool_name, json.dumps(tool_args)[:200])

                tool_result = await execute_tool(tool_name, tool_args, user.id, db, is_admin=user.is_admin)
                tools_used.append({"tool": tool_name, "args": tool_args, "result": tool_result})

                messages.append({"role": "model", "content": [{"functionCall": fc}]})
                messages.append({"role": "user", "content": [{"functionResponse": {"name": tool_name, "response": tool_result}}]})

            continue

        response_text = result.get("text", "")
        if response_text:
            user_message = Message(conversation_id=conversation.id, role="user", content=prompt)
            assistant_message = Message(conversation_id=conversation.id, role="assistant", content=response_text)
            db.add_all([user_message, assistant_message])
            audit_detail = {
                "conversation_id": conversation.id,
                "tools": [t["tool"] for t in tools_used],
                "agent_run_id": prepared.run_id,
            }
            db.add(AuditEvent(user_id=user.id, action="agent.completed",
                              detail_json=json.dumps(audit_detail)))
            db.commit()
            db.refresh(user_message)
            db.refresh(assistant_message)
            return {
                "user_message": {"id": user_message.id, "role": "user", "content": prompt, "created_at": str(user_message.created_at)},
                "assistant_message": {"id": assistant_message.id, "role": "assistant", "content": response_text, "created_at": str(assistant_message.created_at)},
                "tools_used": tools_used,
            }

    fallback = "I completed the requested tasks but ran out of processing steps. Please check the results."
    return {"assistant_message": {"id": "", "role": "assistant", "content": fallback, "created_at": ""}, "tools_used": tools_used}
