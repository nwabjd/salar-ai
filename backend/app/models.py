import secrets
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def token_id() -> str:
    return secrets.token_urlsafe(16)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    whatsapp_auto_reply: Mapped[bool] = mapped_column(Boolean, default=False)
    plan: Mapped[str] = mapped_column(String(32), default="free")
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[Optional[str]] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(240), default="New conversation")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    messages: Mapped[list["Message"]] = relationship(cascade="all, delete-orphan", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(24))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Memory(Base):
    __tablename__ = "memories"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[Optional[str]] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    layer: Mapped[str] = mapped_column(String(32), default="long_term")
    title: Mapped[str] = mapped_column(String(240))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[Optional[str]] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    storage_path: Mapped[str] = mapped_column(Text)
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    token_hash: Mapped[str] = mapped_column(String(255))
    platform: Mapped[str] = mapped_column(String(60), default="windows")
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DeviceSession(Base):
    __tablename__ = "device_sessions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    platform: Mapped[str] = mapped_column(String(60), default="web")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PairingCode(Base):
    __tablename__ = "pairing_codes"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    redeemed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Command(Base):
    __tablename__ = "commands"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(40), default="queued")
    result_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    icon: Mapped[str] = mapped_column(String(20), default="📁")
    color: Mapped[str] = mapped_column(String(20), default="#5227FF")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[Optional[str]] = mapped_column(ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="todo")  # todo, in_progress, done, archived
    priority: Mapped[str] = mapped_column(String(20), default="medium")  # low, medium, high, urgent
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    tags: Mapped[str] = mapped_column(Text, default="")  # comma-separated
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Reminder(Base):
    __tablename__ = "reminders"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[Optional[str]] = mapped_column(ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(240))
    message: Mapped[str] = mapped_column(Text, default="")
    remind_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    recurrence: Mapped[str] = mapped_column(String(30), default="none")  # none, daily, weekly, monthly
    is_done: Mapped[bool] = mapped_column(Boolean, default=False)
    notified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[Optional[str]] = mapped_column(ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120), default="text/plain")
    storage_path: Mapped[str] = mapped_column(Text)
    full_text: Mapped[str] = mapped_column(Text, default="")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="ready")  # processing, ready, error
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Workflow(Base):
    __tablename__ = "workflows"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[Optional[str]] = mapped_column(ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text, default="")
    trigger_type: Mapped[str] = mapped_column(String(40))  # keyword, schedule, email_received, file_created, cron
    trigger_config: Mapped[str] = mapped_column(Text, default="{}")  # JSON config
    actions: Mapped[str] = mapped_column(Text, default="[]")  # JSON array of actions
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), index=True)
    trigger_event: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="running")  # running, success, error
    result_log: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
