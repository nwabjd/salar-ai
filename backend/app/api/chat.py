import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import AuditEvent, Conversation, Document, Memory, Message, User
from ..schemas import ChatRequest, ChatResponse, ConversationCreate, ConversationDetail, ConversationResponse
from ..security import get_current_user


router = APIRouter(tags=["chat"])


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

