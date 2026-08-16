import secrets
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(24), default="running", index=True)
    input_json: Mapped[str] = mapped_column(Text, default="{}")
    output_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str] = mapped_column(Text, default="")
    next_step_sequence: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AgentRunStep(Base):
    __tablename__ = "agent_run_steps"
    __table_args__ = (UniqueConstraint("run_id", "sequence", name="uq_agent_run_step_sequence"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(24))
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    evidence_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Memory(Base):
    __tablename__ = "memories"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[Optional[str]] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    layer: Mapped[str] = mapped_column(String(32), default="long_term")
    title: Mapped[str] = mapped_column(String(240))
    content: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(32), default="memory")  # person, project, file, preference, decision, place, event, memory
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class MemoryRelation(Base):
    __tablename__ = "memory_relations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    from_memory_id: Mapped[str] = mapped_column(ForeignKey("memories.id", ondelete="CASCADE"), index=True)
    to_memory_id: Mapped[str] = mapped_column(ForeignKey("memories.id", ondelete="CASCADE"), index=True)
    relation: Mapped[str] = mapped_column(String(48), default="related")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


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


class WhatsAppContactState(Base):
    __tablename__ = "whatsapp_contact_states"
    __table_args__ = (UniqueConstraint("user_id", "contact_jid", name="uq_whatsapp_owner_contact"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    contact_jid: Mapped[str] = mapped_column(String(255), index=True)
    sender_name: Mapped[str] = mapped_column(String(255), default="")
    introduced: Mapped[bool] = mapped_column(Boolean, default=False)
    history_json: Mapped[str] = mapped_column(Text, default="[]")
    active_topic: Mapped[str] = mapped_column(Text, default="")
    reply_lease_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reply_lease_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


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


class IntelEvent(Base):
    """Unified background-intelligence ledger.

    Every notable thing SALAR notices while working in the background lands here
    (important email, bill due, morning brief, system warning, research finding).
    The assistant surfaces these only when the user asks.
    """

    __tablename__ = "intel_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(48), index=True)  # email_important, email_bill, email_action, brief, system, research, calendar, whatsapp
    severity: Mapped[str] = mapped_column(String(16), default="info")  # info, warning, critical
    source: Mapped[str] = mapped_column(String(48), default="")  # email, calendar, system, research, brief, whatsapp
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str] = mapped_column(Text, default="")
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    evidence_json: Mapped[str] = mapped_column(Text, default="[]")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    seq: Mapped[int] = mapped_column(Integer, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class Job(Base):
    """Durable background job record with compare-and-set lease fencing."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)  # queued, running, completed, failed, cancelled
    priority: Mapped[int] = mapped_column(Integer, default=0)
    input_json: Mapped[str] = mapped_column(Text, default="{}")
    output_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str] = mapped_column(Text, default="")
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    lease_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    workflow_run_id: Mapped[Optional[str]] = mapped_column(ForeignKey("workflow_runs.id", ondelete="SET NULL"), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class JobEvent(Base):
    __tablename__ = "job_events"
    __table_args__ = (UniqueConstraint("job_id", "sequence", name="uq_job_event_sequence"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(24))
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IntelEmailSeen(Base):
    """Deduplicates email scanning so the same message never creates two events."""

    __tablename__ = "intel_email_seen"
    __table_args__ = (UniqueConstraint("user_id", "folder", "message_uid", name="uq_intel_email_seen"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    folder: Mapped[str] = mapped_column(String(80), default="INBOX")
    message_uid: Mapped[str] = mapped_column(String(120), index=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Mission(Base):
    __tablename__ = "missions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    goal: Mapped[str] = mapped_column(Text, default="")
    mode: Mapped[str] = mapped_column(String(16), default="autonomous")
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    plan_json: Mapped[str] = mapped_column(Text, default="[]")
    result_summary: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")
    step_count: Mapped[int] = mapped_column(Integer, default=0)
    completed_count: Mapped[int] = mapped_column(Integer, default=0)
    total_attempts: Mapped[int] = mapped_column(Integer, default=0)
    replan_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class MissionStep(Base):
    __tablename__ = "mission_steps"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    tool: Mapped[str] = mapped_column(String(64))
    args_json: Mapped[str] = mapped_column(Text, default="{}")
    danger_level: Mapped[str] = mapped_column(String(16), default="safe")
    status: Mapped[str] = mapped_column(String(24), default="pending")
    output_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str] = mapped_column(Text, default="")
    approval_note: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MissionEvent(Base):
    __tablename__ = "mission_events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(32))
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PermissionProfile(Base):
    __tablename__ = "permission_profiles"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    levels_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    def levels_dict(self) -> dict:
        import json
        try:
            return json.loads(self.levels_json)
        except Exception:
            return {}


class ActionLog(Base):
    __tablename__ = "action_logs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(16), default="chat")  # chat, mission, device, workflow
    tool: Mapped[str] = mapped_column(String(64))
    args_json: Mapped[str] = mapped_column(Text, default="{}")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    before_state_json: Mapped[str] = mapped_column(Text, default="{}")
    undo_action_json: Mapped[str] = mapped_column(Text, default="")
    is_undoable: Mapped[bool] = mapped_column(Boolean, default=False)
    undo_status: Mapped[str] = mapped_column(String(16), default="none")  # none, undoable, undone, undo_failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DeepResearch(Base):
    __tablename__ = "deep_research"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    goal: Mapped[str] = mapped_column(Text, default="")
    agents_json: Mapped[str] = mapped_column(Text, default="[]")
    synthesis_json: Mapped[str] = mapped_column(Text, default="{}")
    findings_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(24), default="running")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ContactProfile(Base):
    __tablename__ = "contact_profiles"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    email: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(64), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ContactInteraction(Base):
    __tablename__ = "contact_interactions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contact_profiles.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))  # conversation, meeting, project, follow_up, note
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Bookmark(Base):
    __tablename__ = "bookmarks"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(1024))
    title: Mapped[str] = mapped_column(String(300), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VoicePreferences(Base):
    __tablename__ = "voice_preferences"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    voice: Mapped[str] = mapped_column(String(120), default="en-US-AriaNeural")
    style: Mapped[str] = mapped_column(String(32), default="neutral")   # neutral, cheerful, serious, whisper, energetic
    personality: Mapped[str] = mapped_column(String(32), default="default")  # default, professional, friendly, concise
    rate: Mapped[str] = mapped_column(String(16), default="+0%")
    pitch: Mapped[str] = mapped_column(String(16), default="+0Hz")
    wake_word_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    wake_phrase: Mapped[str] = mapped_column(String(64), default="hey salar")
    interruption_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)  # intel, alert, mission, system, email
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str] = mapped_column(String(300), default="")
    severity: Mapped[str] = mapped_column(String(16), default="info")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Consent(Base):
    __tablename__ = "consents"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    granted: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class PrivacyPreferences(Base):
    __tablename__ = "privacy_preferences"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    local_ai_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    data_retention_days: Mapped[int] = mapped_column(Integer, default=30)
    action_log_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    intel_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    analytics_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class PushToken(Base):
    __tablename__ = "push_tokens"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), nullable=True, index=True)
    platform: Mapped[str] = mapped_column(String(40))  # web_push, fcm, apns
    token: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class SyncState(Base):
    __tablename__ = "sync_states"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    pending_commands: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Plugin(Base):
    __tablename__ = "plugins"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    version: Mapped[str] = mapped_column(String(32), default="0.1.0")
    description: Mapped[str] = mapped_column(Text, default="")
    author: Mapped[str] = mapped_column(String(120), default="")
    manifest_json: Mapped[str] = mapped_column(Text, default="{}")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class MediaMemory(Base):
    __tablename__ = "media_memories"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(24))  # image, audio, video
    caption: Mapped[str] = mapped_column(Text, default="")
    transcript: Mapped[str] = mapped_column(Text, default="")
    storage_path: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WidgetPrefs(Base):
    __tablename__ = "widget_prefs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    widgets_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class CoreTask(Base):
    __tablename__ = "core_tasks"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    request: Mapped[str] = mapped_column(Text)
    goal: Mapped[str] = mapped_column(Text, default="")
    intent_kind: Mapped[str] = mapped_column(String(32), default="chat", index=True)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    trace_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class CoreTrace(Base):
    __tablename__ = "core_traces"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("core_tasks.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="running", index=True)
    steps_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class CoreTraceStep(Base):
    __tablename__ = "core_trace_steps"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    trace_id: Mapped[str] = mapped_column(ForeignKey("core_traces.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(40))
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class CoreEventLog(Base):
    __tablename__ = "core_event_log"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    trace_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    payload: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorldEntity(Base):
    """A node in the user's continuously-updated world model.

    Each entity is deduplicated by (user, entity_type, canonical key). The
    canonical key is a stable, lower-cased identifier within its type (e.g.
    ``project:aurora`` or ``person:alice@example.com``) so repeated observations
    of the same thing merge into one node with provenance (source, first/last
    seen, confidence). Entities can expire when no observation refreshes them.
    """

    __tablename__ = "world_entities"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    key: Mapped[str] = mapped_column(String(320), index=True)
    name: Mapped[str] = mapped_column(String(240), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    props_json: Mapped[str] = mapped_column(Text, default="{}")
    source: Mapped[str] = mapped_column(String(64), default="")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ttl_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    __table_args__ = (UniqueConstraint("user_id", "entity_type", "key", name="uq_world_entity_user_type_key"),)

    @property
    def props(self) -> dict:
        import json as _json
        try:
            return _json.loads(self.props_json or "{}")
        except Exception:
            return {}


class WorldRelation(Base):
    """A typed edge between two WorldEntity nodes."""

    __tablename__ = "world_relations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    from_id: Mapped[str] = mapped_column(ForeignKey("world_entities.id", ondelete="CASCADE"), index=True)
    to_id: Mapped[str] = mapped_column(ForeignKey("world_entities.id", ondelete="CASCADE"), index=True)
    relation: Mapped[str] = mapped_column(String(48), index=True)
    source: Mapped[str] = mapped_column(String(64), default="")
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ttl_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    __table_args__ = (UniqueConstraint("user_id", "from_id", "to_id", "relation", name="uq_world_relation_user_from_to_rel"),)


class WorldObservation(Base):
    """A journaled raw observation that fed (or will feed) the world graph.

    Kept so provenance can be traced back to the exact event, tool call, or
    sensor reading that produced or refreshed an entity/relation.
    """

    __tablename__ = "world_observations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[Optional[str]] = mapped_column(ForeignKey("world_entities.id", ondelete="SET NULL"), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorldActionExecution(Base):
    """A recorded execution of a proposed world-model action.

    Each entry logs which situation_kind + action was executed, which tool
    calls it issued, how it turned out, and whether the underlying situation
    was later resolved. Self-evolution aggregates these rows into learned
    action policies.
    """

    __tablename__ = "world_action_executions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    situation_kind: Mapped[str] = mapped_column(String(64), index=True)
    action_title: Mapped[str] = mapped_column(String(240), default="")
    tool_calls_json: Mapped[str] = mapped_column(Text, default="[]")
    outcome: Mapped[str] = mapped_column(String(24), default="unknown")  # success | failure | neutral | unknown
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorldActionPolicy(Base):
    """Learned per-user policy: how well a given action resolves a situation.

    score is a bounded success measure (0..1) derived from executions.
    """

    __tablename__ = "world_action_policies"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    situation_kind: Mapped[str] = mapped_column(String(64), index=True)
    action_title: Mapped[str] = mapped_column(String(240), default="")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    successes: Mapped[int] = mapped_column(Integer, default=0)
    resolved_count: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("user_id", "situation_kind", "action_title", name="uq_world_policy_user_kind_action"),)
