from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base


class Chatbot(Base):
    __tablename__ = "chatbots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    website_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(100), nullable=True)
    behavior_profile: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, ingesting, ready, error
    status_json: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    # Website understanding layer — generated during ingestion
    site_profile: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chatbot_id: Mapped[int] = mapped_column(ForeignKey("chatbots.id", ondelete="CASCADE"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    session_id: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    from sqlalchemy import UniqueConstraint
    __table_args__ = (UniqueConstraint("session_id", "chatbot_id", name="uq_session_chatbot"),)



class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), nullable=True)
    role: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UploadedDocument(Base):
    __tablename__ = "uploaded_documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chatbot_id: Mapped[int | None] = mapped_column(ForeignKey("chatbots.id", ondelete="CASCADE"), nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    source_path: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(100))
    file_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EmbeddingMetadata(Base):
    __tablename__ = "embedding_metadata"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("uploaded_documents.id", ondelete="CASCADE"))
    chunk_id: Mapped[str] = mapped_column(String(128), index=True)
    text: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="user")
    
    # Settings & Preferences
    theme: Mapped[str] = mapped_column(String(16), default="dark")
    private_inference: Mapped[bool] = mapped_column(Integer, default=0) # SQLite uses Integer for bool
    
    is_active: Mapped[bool] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SessionMemory(Base):
    __tablename__ = "session_memory"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(128), index=True)
    chatbot_id: Mapped[int] = mapped_column(ForeignKey("chatbots.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    value: Mapped[str] = mapped_column(Text)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(128))
    resource: Mapped[str | None] = mapped_column(String(128))
    details: Mapped[str | None] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SystemConfig(Base):
    __tablename__ = "system_configs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text)


class ConversationGoal(Base):
    __tablename__ = "conversation_goals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(128), index=True)
    chatbot_id: Mapped[int] = mapped_column(ForeignKey("chatbots.id", ondelete="CASCADE"), index=True)
    
    current_goal: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active_workflow: Mapped[str | None] = mapped_column(String(100), nullable=True)
    workflow_stage: Mapped[str] = mapped_column(String(50), default="browsing")
    conversation_mode: Mapped[str] = mapped_column(String(50), default="exploratory")
    
    # Store discovered entities, related pages, and completed steps as JSON
    state_json: Mapped[dict] = mapped_column(JSON, default=dict)
    
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    from sqlalchemy import UniqueConstraint
    __table_args__ = (UniqueConstraint("session_id", "chatbot_id", name="uq_session_goal"),)


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chatbot_id: Mapped[int] = mapped_column(ForeignKey("chatbots.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, ingesting, ready, error
    current_stage: Mapped[str] = mapped_column(String(50), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    total_chunks: Mapped[int] = mapped_column(Integer, default=0)
    indexed_chunks: Mapped[int] = mapped_column(Integer, default=0)
    failed_chunks: Mapped[int] = mapped_column(Integer, default=0)
    
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Task metadata
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
