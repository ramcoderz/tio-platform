from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict

from backend.db.session import get_db
from backend.models.entities import User, Chatbot, Message, Conversation, UploadedDocument
from backend.api.auth import get_current_user
from backend.utils.logging_collector import admin_log_handler
from backend.utils.monitoring import get_stats_snapshot

router = APIRouter(tags=["admin"])

async def ensure_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user

@router.get("/logs", dependencies=[Depends(ensure_admin)])
async def get_system_logs():
    """
    Returns the last N system logs captured in memory.
    """
    return {"logs": admin_log_handler.get_logs()}

@router.get("/stats", dependencies=[Depends(ensure_admin)])
async def get_system_stats(db: AsyncSession = Depends(get_db)):
    """
    Returns high-level system statistics for the dashboard.
    """
    user_count = await db.scalar(select(func.count(User.id)))
    chatbot_count = await db.scalar(select(func.count(Chatbot.id)))
    message_count = await db.scalar(select(func.count(Message.id)))
    doc_count = await db.scalar(select(func.count(UploadedDocument.id)))
    
    # Active sessions (last 24h)
    active_sessions = await db.scalar(select(func.count(Conversation.id)))

    # Real-time monitoring stats
    monitor = get_stats_snapshot()

    return {
        "users": user_count or 0,
        "chatbots": chatbot_count or 0,
        "messages": message_count or 0,
        "documents": doc_count or 0,
        "sessions": active_sessions or 0,
        "system_status": "healthy",
        "monitor": monitor
    }

@router.get("/monitoring", dependencies=[Depends(ensure_admin)])
async def get_monitoring_data():
    """
    Direct access to real-time query monitoring metrics.
    """
    return get_stats_snapshot()

@router.get("/chatbots/monitor", dependencies=[Depends(ensure_admin)])
async def monitor_chatbots(db: AsyncSession = Depends(get_db)):
    """
    Returns a list of all chatbots with their ingestion status and resource usage.
    """
    result = await db.execute(select(Chatbot).order_by(Chatbot.created_at.desc()))
    chatbots = result.scalars().all()
    
    monitored = []
    for cb in chatbots:
        monitored.append({
            "id": cb.id,
            "name": cb.name,
            "status": cb.status,
            "domain": cb.domain,
            "created_at": cb.created_at
        })
    return monitored
