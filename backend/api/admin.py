"""
TiO Admin API — Operational monitoring console endpoints.
All routes require admin role via ensure_admin dependency.
Mounted at /api/internal/*
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Optional
import asyncio

from backend.db.session import get_db
from backend.models.entities import (
    User, Chatbot, Message, Conversation,
    UploadedDocument, EmbeddingMetadata, AuditLog, SessionMemory
)
from backend.api.auth import get_current_user
from backend.utils.logging_collector import admin_log_handler
from backend.utils.monitoring import get_stats_snapshot
from backend.utils.api_usage_tracker import get_api_usage_snapshot

router = APIRouter(tags=["admin"])


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

async def ensure_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user


# ---------------------------------------------------------------------------
# Overview Stats
# ---------------------------------------------------------------------------

@router.get("/stats", dependencies=[Depends(ensure_admin)])
async def get_system_stats(db: AsyncSession = Depends(get_db)):
    """High-level system statistics."""
    user_count      = await db.scalar(select(func.count(User.id)))
    chatbot_count   = await db.scalar(select(func.count(Chatbot.id)))
    message_count   = await db.scalar(select(func.count(Message.id)))
    doc_count       = await db.scalar(select(func.count(UploadedDocument.id)))
    session_count   = await db.scalar(select(func.count(Conversation.id)))
    ready_bots      = await db.scalar(select(func.count(Chatbot.id)).where(Chatbot.status == "ready"))
    error_bots      = await db.scalar(select(func.count(Chatbot.id)).where(Chatbot.status == "error"))
    ingesting_bots  = await db.scalar(select(func.count(Chatbot.id)).where(Chatbot.status == "ingesting"))

    return {
        "users":          user_count or 0,
        "chatbots":       chatbot_count or 0,
        "chatbots_ready": ready_bots or 0,
        "chatbots_error": error_bots or 0,
        "chatbots_ingesting": ingesting_bots or 0,
        "messages":       message_count or 0,
        "documents":      doc_count or 0,
        "sessions":       session_count or 0,
        "system_status":  "healthy",
        "monitor":        get_stats_snapshot(),
    }


# ---------------------------------------------------------------------------
# System Logs
# ---------------------------------------------------------------------------

@router.get("/logs", dependencies=[Depends(ensure_admin)])
async def get_system_logs(
    level: Optional[str] = Query(None, description="Filter by level: ERROR, WARNING, INFO"),
    limit: int = Query(200, le=500)
):
    """Returns in-memory system logs, optionally filtered by level."""
    logs = admin_log_handler.get_logs()
    if level:
        logs = [l for l in logs if l["level"] == level.upper()]
    return {"logs": logs[-limit:]}


# ---------------------------------------------------------------------------
# API Usage
# ---------------------------------------------------------------------------

@router.get("/api-usage", dependencies=[Depends(ensure_admin)])
async def get_api_usage():
    """Live API call counters for all providers."""
    return get_api_usage_snapshot()


# ---------------------------------------------------------------------------
# Monitoring / Retrieval Quality
# ---------------------------------------------------------------------------

@router.get("/monitoring", dependencies=[Depends(ensure_admin)])
async def get_monitoring_data():
    """Real-time retrieval quality and query monitoring metrics."""
    return get_stats_snapshot()


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@router.get("/users", dependencies=[Depends(ensure_admin)])
async def list_users(db: AsyncSession = Depends(get_db)):
    """All users with usage statistics."""
    users = (await db.execute(
        select(User).order_by(User.created_at.desc())
    )).scalars().all()

    result = []
    for u in users:
        chatbot_count = await db.scalar(
            select(func.count(Chatbot.id)).where(Chatbot.user_id == u.id)
        )
        message_count = await db.scalar(
            select(func.count(Message.id))
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(Conversation.user_id == u.id)
        )
        session_count = await db.scalar(
            select(func.count(Conversation.id)).where(Conversation.user_id == u.id)
        )
        # Most recent message timestamp
        last_msg = await db.scalar(
            select(func.max(Message.created_at))
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(Conversation.user_id == u.id)
        )
        result.append({
            "id":             u.id,
            "username":       u.username,
            "email":          u.email,
            "role":           u.role,
            "is_active":      bool(u.is_active),
            "created_at":     u.created_at.isoformat() if u.created_at else None,
            "chatbot_count":  chatbot_count or 0,
            "message_count":  message_count or 0,
            "session_count":  session_count or 0,
            "last_active":    last_msg.isoformat() if last_msg else None,
        })
    return result


@router.get("/users/{user_id}/history", dependencies=[Depends(ensure_admin)])
async def get_user_history(user_id: int, limit: int = Query(50, le=200), db: AsyncSession = Depends(get_db)):
    """Full chat history for a specific user across all chatbots."""
    conversations = (await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.created_at.desc())
    )).scalars().all()

    result = []
    for conv in conversations:
        chatbot = await db.get(Chatbot, conv.chatbot_id)
        messages = (await db.execute(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at.asc())
            .limit(limit)
        )).scalars().all()
        result.append({
            "conversation_id": conv.id,
            "session_id":      conv.session_id,
            "chatbot_id":      conv.chatbot_id,
            "chatbot_name":    chatbot.name if chatbot else "Unknown",
            "started_at":      conv.created_at.isoformat() if conv.created_at else None,
            "messages": [
                {
                    "id":         m.id,
                    "role":       m.role,
                    "content":    m.content,
                    "confidence": m.confidence,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in messages
            ],
        })
    return result


@router.post("/users/{user_id}/suspend", dependencies=[Depends(ensure_admin)])
async def suspend_user(user_id: int, db: AsyncSession = Depends(get_db)):
    """Toggle suspension status for a user."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == "admin":
        raise HTTPException(status_code=403, detail="Cannot suspend another admin")
    user.is_active = 0 if user.is_active else 1
    await db.commit()
    return {"user_id": user_id, "is_active": bool(user.is_active)}


@router.delete("/users/{user_id}", dependencies=[Depends(ensure_admin)])
async def delete_user_admin(user_id: int, db: AsyncSession = Depends(get_db)):
    """Hard delete a user and all their data."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == "admin":
        raise HTTPException(status_code=403, detail="Cannot delete an admin account")

    # Deep delete all chatbots
    from backend.utils.cleanup import deep_delete_chatbot
    chatbots = (await db.execute(
        select(Chatbot).where(Chatbot.user_id == user_id)
    )).scalars().all()
    for cb in chatbots:
        await deep_delete_chatbot(cb.id, db)

    # Delete conversations + messages
    convs = (await db.execute(
        select(Conversation).where(Conversation.user_id == user_id)
    )).scalars().all()
    for conv in convs:
        await db.execute(delete(Message).where(Message.conversation_id == conv.id))
        await db.delete(conv)

    await db.delete(user)
    await db.commit()
    return {"status": "deleted", "user_id": user_id}


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

@router.get("/sessions", dependencies=[Depends(ensure_admin)])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    """All active conversations with metadata."""
    conversations = (await db.execute(
        select(Conversation).order_by(Conversation.created_at.desc())
    )).scalars().all()

    result = []
    for conv in conversations:
        chatbot = await db.get(Chatbot, conv.chatbot_id)
        user    = await db.get(User, conv.user_id) if conv.user_id else None
        msg_count = await db.scalar(
            select(func.count(Message.id)).where(Message.conversation_id == conv.id)
        )
        last_msg = await db.scalar(
            select(func.max(Message.created_at)).where(Message.conversation_id == conv.id)
        )
        result.append({
            "id":           conv.id,
            "session_id":   conv.session_id,
            "chatbot_id":   conv.chatbot_id,
            "chatbot_name": chatbot.name if chatbot else "Unknown",
            "user_id":      conv.user_id,
            "username":     user.username if user else "Anonymous",
            "message_count": msg_count or 0,
            "started_at":   conv.created_at.isoformat() if conv.created_at else None,
            "last_message": last_msg.isoformat() if last_msg else None,
        })
    return result


@router.delete("/sessions/{session_id}", dependencies=[Depends(ensure_admin)])
async def force_clear_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Admin force-clear a session by session_id."""
    convs = (await db.execute(
        select(Conversation).where(Conversation.session_id == session_id)
    )).scalars().all()

    if not convs:
        raise HTTPException(status_code=404, detail="Session not found")

    for conv in convs:
        await db.execute(delete(Message).where(Message.conversation_id == conv.id))
        await db.delete(conv)

    await db.execute(delete(SessionMemory).where(SessionMemory.session_id == session_id))
    await db.commit()
    return {"status": "cleared", "session_id": session_id}


# ---------------------------------------------------------------------------
# Ingestion / Chatbot Monitoring
# ---------------------------------------------------------------------------

@router.get("/ingestion/status", dependencies=[Depends(ensure_admin)])
async def get_ingestion_status(db: AsyncSession = Depends(get_db)):
    """All chatbots with full ingestion health details."""
    chatbots = (await db.execute(
        select(Chatbot).order_by(Chatbot.created_at.desc())
    )).scalars().all()

    result = []
    for cb in chatbots:
        doc_count = await db.scalar(
            select(func.count(UploadedDocument.id)).where(UploadedDocument.chatbot_id == cb.id)
        )
        chunk_count = await db.scalar(
            select(func.count(EmbeddingMetadata.id))
            .join(UploadedDocument, EmbeddingMetadata.document_id == UploadedDocument.id)
            .where(UploadedDocument.chatbot_id == cb.id)
        )
        profile = cb.site_profile or {}
        result.append({
            "id":              cb.id,
            "name":            cb.name,
            "status":          cb.status,
            "domain":          cb.domain,
            "website_url":     cb.website_url,
            "created_at":      cb.created_at.isoformat() if cb.created_at else None,
            "doc_count":       doc_count or 0,
            "chunk_count":     chunk_count or 0,
            "error_message":   cb.error_message,
            "has_site_profile": bool(profile),
            "site_summary":    profile.get("site_summary", ""),
            "top_entities":    profile.get("top_entities", [])[:8],
            "pages_crawled":   profile.get("pages_crawled", 0),
            "services":        profile.get("services", []),
        })
    return result


@router.post("/chatbots/{chatbot_id}/delete", dependencies=[Depends(ensure_admin)])
async def admin_delete_chatbot(chatbot_id: int, db: AsyncSession = Depends(get_db)):
    """Admin force-delete any chatbot with full vector + file cleanup."""
    from backend.utils.cleanup import deep_delete_chatbot
    chatbot = await db.get(Chatbot, chatbot_id)
    if not chatbot:
        raise HTTPException(status_code=404, detail="Chatbot not found")
    await deep_delete_chatbot(chatbot_id, db)
    return {"status": "deleted", "chatbot_id": chatbot_id}


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

@router.get("/documents", dependencies=[Depends(ensure_admin)])
async def list_all_documents(db: AsyncSession = Depends(get_db)):
    """All uploaded documents with chunk counts."""
    docs = (await db.execute(
        select(UploadedDocument).order_by(UploadedDocument.created_at.desc())
    )).scalars().all()
    result = []
    for d in docs:
        chunk_count = await db.scalar(
            select(func.count(EmbeddingMetadata.id)).where(EmbeddingMetadata.document_id == d.id)
        )
        result.append({
            "id":          d.id,
            "filename":    d.filename,
            "type":        d.content_type,
            "chatbot_id":  d.chatbot_id,
            "source_path": d.source_path,
            "chunk_count": chunk_count or 0,
            "created_at":  d.created_at.isoformat() if d.created_at else None,
        })
    return result


@router.delete("/documents/{doc_id}", dependencies=[Depends(ensure_admin)])
async def admin_delete_document(doc_id: int, db: AsyncSession = Depends(get_db)):
    """Admin delete any document with vector + file cleanup."""
    from backend.vectorstore.service import delete_chunk_vectors
    import os

    doc = await db.get(UploadedDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    chunk_rows = (await db.execute(
        select(EmbeddingMetadata).where(EmbeddingMetadata.document_id == doc_id)
    )).scalars().all()
    chunk_ids = [c.chunk_id for c in chunk_rows]
    if chunk_ids:
        await asyncio.to_thread(delete_chunk_vectors, chunk_ids)
    await db.execute(delete(EmbeddingMetadata).where(EmbeddingMetadata.document_id == doc_id))

    if doc.source_path and os.path.exists(doc.source_path):
        try:
            os.remove(doc.source_path)
        except Exception:
            pass

    await db.delete(doc)
    await db.commit()
    return {"status": "deleted", "doc_id": doc_id, "chunks_removed": len(chunk_ids)}


# ---------------------------------------------------------------------------
# Domain Routing
# ---------------------------------------------------------------------------

@router.get("/domain-routing", dependencies=[Depends(ensure_admin)])
async def get_domain_routing(db: AsyncSession = Depends(get_db)):
    """Domain detection distribution and routing health from monitoring."""
    monitor = get_stats_snapshot()
    return {
        "domain_distribution": monitor.get("domain_distribution", {}),
        "domain_mismatches":   monitor.get("domain_mismatches", 0),
        "recent_warnings":     [
            w for w in monitor.get("recent_warnings", [])
            if w.get("type") == "domain_mismatch"
        ],
        "chatbot_domains": (await _get_chatbot_domains(db)),
    }


async def _get_chatbot_domains(db: AsyncSession):
    chatbots = (await db.execute(select(Chatbot))).scalars().all()
    return [
        {"id": cb.id, "name": cb.name, "domain": cb.domain or "undetected", "status": cb.status}
        for cb in chatbots
    ]


# ---------------------------------------------------------------------------
# Retrieval Quality
# ---------------------------------------------------------------------------

@router.get("/retrieval/quality", dependencies=[Depends(ensure_admin)])
async def get_retrieval_quality():
    """Retrieval health: confidence scores, empty retrievals, weak grounding."""
    monitor = get_stats_snapshot()
    return {
        "total_queries":         monitor.get("total_queries", 0),
        "unanswered_queries":    monitor.get("unanswered_queries", 0),
        "weak_grounding_events": monitor.get("weak_grounding_events", 0),
        "fallback_events":       monitor.get("fallback_events", 0),
        "hallucination_warnings":monitor.get("hallucination_warnings", 0),
        "avg_confidence":        monitor.get("avg_confidence", 0),
        "avg_retrieval_ms":      monitor.get("avg_retrieval_ms", 0),
        "answer_rate_pct":       monitor.get("answer_rate_pct", 100),
        "recent_unanswered":     monitor.get("recent_unanswered", []),
        "recent_fallbacks":      monitor.get("recent_fallbacks", []),
        "recent_warnings":       monitor.get("recent_warnings", []),
        "recent_queries":        monitor.get("recent_queries", []),
    }


# ---------------------------------------------------------------------------
# Cleanup / Purge
# ---------------------------------------------------------------------------

@router.post("/cleanup/all", dependencies=[Depends(ensure_admin)])
async def cleanup_all(db: AsyncSession = Depends(get_db)):
    """Purge all messages, conversations, and documents (nuclear option)."""
    await db.execute(delete(Message))
    await db.execute(delete(Conversation))
    await db.execute(delete(UploadedDocument))
    await db.commit()
    return {"status": "purged"}
