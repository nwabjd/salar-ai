from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class SupabaseExchangeRequest(BaseModel):
    token: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    is_admin: bool
    created_at: datetime


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    status: str = "active"
    goals: List[str] = []
    deadline: Optional[datetime] = None


class ProjectResponse(ProjectCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime


class ConversationCreate(BaseModel):
    title: str = "New conversation"
    project_id: Optional[str] = None


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    role: str
    content: str
    created_at: datetime


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    project_id: Optional[str]
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationResponse):
    messages: List[MessageResponse]


class ChatRequest(BaseModel):
    conversation_id: str
    content: str
    fast: bool = False


class ChatResponse(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse


class MemoryCreate(BaseModel):
    title: str
    content: str
    layer: str = "long_term"
    project_id: Optional[str] = None
    tags: List[str] = []
    strength: float = 1.0
    expires_at: Optional[datetime] = None


class MemoryResponse(MemoryCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    expired: bool
    encrypted: bool
    created_at: datetime
    updated_at: datetime


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    filename: str
    media_type: str
    project_id: Optional[str]
    created_at: datetime


class DocumentSearchResult(DocumentResponse):
    snippet: str


class AttachmentCreate(BaseModel):
    conversation_id: Optional[str] = None


class AttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    filename: str
    media_type: str
    size_bytes: int
    analysis: Optional[str] = None
    conversation_id: Optional[str] = None
    created_at: datetime


class DeviceCreate(BaseModel):
    name: str
    platform: str = "windows"


class DeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    platform: str
    last_seen_at: Optional[datetime]
    created_at: datetime


class DeviceRegistration(DeviceResponse):
    token: str


class CommandCreate(BaseModel):
    device_id: str
    kind: str
    payload: Dict[str, Any] = {}


class CommandResponse(BaseModel):
    id: str
    device_id: str
    kind: str
    payload: Dict[str, Any]
    status: str
    result: Optional[Dict[str, Any]]
    requires_confirmation: bool
    created_at: datetime
    completed_at: Optional[datetime]


class CommandResult(BaseModel):
    ok: bool
    detail: str = ""
    data: Dict[str, Any] = {}


