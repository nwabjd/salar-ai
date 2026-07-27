import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import AuditEvent, Conversation, Document, Memory, Message, User
from ..schemas import ChatRequest, ChatResponse, ConversationCreate, ConversationDetail, ConversationResponse
from ..security import get_current_user
from .agent import TOOL_DEFINITIONS, execute_tool

log = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

MAX_AGENT_ROUNDS = 5


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
):
    conversation = owned_conversation(db, user.id, payload.conversation_id)
    prompt = payload.content.strip()
    if not prompt:
        raise HTTPException(status_code=422, detail="Message cannot be empty")
    history = list(conversation.messages)
    memories = list(db.scalars(select(Memory).where(Memory.user_id == user.id).order_by(Memory.updated_at.desc()).limit(12)))
    documents = list(db.scalars(select(Document).where(Document.user_id == user.id).order_by(Document.created_at.desc()).limit(6)))
    response_text = await request.app.state.coordinator.reply(
        prompt=prompt, messages=history, memories=memories, documents=documents
    )
    user_message = Message(conversation_id=conversation.id, role="user", content=prompt)
    assistant_message = Message(conversation_id=conversation.id, role="assistant", content=response_text)
    db.add_all([user_message, assistant_message])
    db.flush()
    db.add(
        AuditEvent(
            user_id=user.id,
            action="chat.completed",
            detail_json=json.dumps({"conversation_id": conversation.id}),
        )
    )
    db.commit()
    db.refresh(user_message)
    db.refresh(assistant_message)
    return ChatResponse(user_message=user_message, assistant_message=assistant_message)


@router.post("/api/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conversation = owned_conversation(db, user.id, payload.conversation_id)
    prompt = payload.content.strip()
    if not prompt:
        raise HTTPException(status_code=422, detail="Message cannot be empty")
    fast = getattr(payload, "fast", False)
    history = list(conversation.messages)

    user_message = Message(conversation_id=conversation.id, role="user", content=prompt)
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    coordinator = request.app.state.coordinator
    gemini = coordinator.gemini

    async def generate():
        full_response = []

        if fast:
            agent_system = (
                "You are SALAR, a voice assistant. Reply in 1-2 short sentences max. "
                "Be direct, natural, and conversational — like talking to someone next to you. "
                "No bullet points, no formatting, no markdown. Just plain spoken English. "
                "After using a tool, immediately tell the user the result in a natural sentence."
            )
        else:
            search_results = await coordinator._search_with_timeout(prompt)
            context_parts = []
            memories = list(db.scalars(select(Memory).where(Memory.user_id == user.id).order_by(Memory.updated_at.desc()).limit(12)))
            documents = list(db.scalars(select(Document).where(Document.user_id == user.id).order_by(Document.created_at.desc()).limit(6)))
            memory_text = "\n".join(f"- {m.title}: {m.content}" for m in memories)
            if memory_text:
                context_parts.append(f"Relevant saved memory:\n{memory_text}")
            document_text = "\n".join(f"- {d.filename}: {(getattr(d, 'extracted_text', None) or '')[:800]}" for d in documents)
            if document_text:
                context_parts.append(f"Relevant documents:\n{document_text}")
            if search_results:
                context_parts.append(f"Web search results:\n{search_results}")

            system = coordinator.build_payload(
                prompt=prompt, messages=history, memories=memories,
                documents=documents, search_results=search_results,
            )
            system_text = system[0]["content"] if system else ""
            agent_system = (
                "You are SALAR, a concise and helpful private AI assistant with PC control. "
                "Use available tools when the user asks you to do something on their computer. "
                "Always be helpful, concise, and confirm actions. "
                "CRITICAL: After ANY tool call, you MUST reply with a natural-language message to the user summarizing the result. "
                "Never leave the user without a spoken response. If a tool returns a time, temperature, file list, etc., tell the user what it said in plain English."
            )
            if context_parts:
                agent_system += "\n\n" + "\n\n".join(context_parts)

        messages = [{"role": "system", "content": agent_system}]
        messages.extend({"role": m.role, "content": m.content} for m in history[-12:])
        messages.append({"role": "user", "content": prompt})

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

                        tool_result = await execute_tool(tool_name, tool_args, user.id, save_db)
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
            assistant_msg = Message(conversation_id=conversation.id, role="assistant", content=response_text)
            save_db.add(assistant_msg)
            save_db.add(AuditEvent(
                user_id=user.id, action="chat.completed",
                detail_json=json.dumps({"conversation_id": conversation.id, "tools": [t["tool"] for t in tools_used]}),
            ))
            save_db.commit()
            save_db.refresh(assistant_msg)
            yield f"data: {json.dumps({'type': 'done', 'message_id': assistant_msg.id, 'created_at': str(assistant_msg.created_at)})}\n\n"
        except Exception as e:
            log.error("Agent stream failed: %s", e, exc_info=True)
            fallback = "The AI service is temporarily unavailable. Your message was saved — please try again."
            full_response.append(fallback)
            yield f"data: {json.dumps({'type': 'token', 'content': fallback})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'message_id': '', 'created_at': ''})}\n\n"
        finally:
            save_db.close()

    return StreamingResponse(generate(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "Content-Encoding": "identity",
    })
