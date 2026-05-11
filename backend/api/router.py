from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
import os
import asyncio

from backend.db.session import get_db
from backend.models.entities import Chatbot, UploadedDocument, Conversation, Message, EmbeddingMetadata, SessionMemory
from backend.memory.service import get_or_create_conversation, add_message, recent_history, get_all_history
from backend.ingestion.service import ingest_file, ingest_website
from backend.agents.orchestrator_agent import run_orchestration
from backend.vectorstore.service import delete_chatbot_vectors
from backend.config.settings import get_settings

settings = get_settings()
api_router = APIRouter()

# --- Schemas ---

class ChatbotCreate(BaseModel):
    name: str | None = None
    website_url: str | None = None

class ChatReq(BaseModel):
    chatbot_id: int
    session_id: str
    message: str

# --- Chatbot Management ---

@api_router.post("/chatbots")
async def create_chatbot(payload: ChatbotCreate, db: AsyncSession = Depends(get_db)):
    # Auto-generate title if not provided
    name = payload.name
    if not name and payload.website_url:
        from urllib.parse import urlparse
        domain = urlparse(payload.website_url).netloc
        if domain:
            name = domain.replace("www.", "").split('.')[0].capitalize() + " Assistant"
        else:
            name = "New Chatbot"
    
    chatbot = Chatbot(
        name=name or "New Chatbot",
        website_url=payload.website_url,
        status="pending"
    )
    db.add(chatbot)
    await db.commit()
    await db.refresh(chatbot)
    
    # Trigger ingestion if website URL provided
    if payload.website_url:
        asyncio.create_task(ingest_website(chatbot.id, payload.website_url))
        
    return chatbot

@api_router.get("/chatbots")
async def list_chatbots(db: AsyncSession = Depends(get_db)):
    stmt = select(Chatbot).order_by(Chatbot.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()

@api_router.get("/chatbots/{chatbot_id}")
async def get_chatbot(chatbot_id: int, db: AsyncSession = Depends(get_db)):
    chatbot = await db.get(Chatbot, chatbot_id)
    if not chatbot:
        raise HTTPException(status_code=404, detail="Chatbot not found")
    return chatbot

@api_router.delete("/chatbots/{chatbot_id}")
async def delete_chatbot(chatbot_id: int, db: AsyncSession = Depends(get_db)):
    chatbot = await db.get(Chatbot, chatbot_id)
    if not chatbot:
        raise HTTPException(status_code=404, detail="Chatbot not found")
    
    # 1. Physical File Cleanup
    stmt = select(UploadedDocument).where(UploadedDocument.chatbot_id == chatbot_id)
    docs = (await db.execute(stmt)).scalars().all()
    for d in docs:
        if d.storage_path and os.path.exists(d.storage_path):
            try: os.remove(d.storage_path)
            except: pass
    
    # 2. Vector Cleanup
    await asyncio.to_thread(delete_chatbot_vectors, chatbot_id)
    
    # 3. Database Cleanup (Cascades will handle related rows)
    await db.delete(chatbot)
    await db.commit()
    
    return {"status": "deleted"}

# --- Ingestion ---

@api_router.post("/chatbots/{chatbot_id}/upload")
async def upload_document(chatbot_id: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    chatbot = await db.get(Chatbot, chatbot_id)
    if not chatbot:
        raise HTTPException(status_code=404, detail="Chatbot not found")
    
    return await ingest_file(chatbot_id, file, db)

@api_router.get("/chatbots/{chatbot_id}/files")
async def list_chatbot_files(chatbot_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(UploadedDocument).where(UploadedDocument.chatbot_id == chatbot_id)
    result = await db.execute(stmt)
    docs = result.scalars().all()
    
    res = []
    for d in docs:
        chunk_count = (await db.execute(select(func.count(EmbeddingMetadata.id)).where(EmbeddingMetadata.document_id == d.id))).scalar()
        res.append({
            "id": d.id,
            "filename": d.filename,
            "type": d.content_type,
            "chunks": chunk_count,
            "created_at": d.created_at.isoformat()
        })
    return res

# --- Chat ---

@api_router.post("/chat")
async def chat(payload: ChatReq, db: AsyncSession = Depends(get_db)):
    chatbot = await db.get(Chatbot, payload.chatbot_id)
    if not chatbot:
        raise HTTPException(status_code=404, detail="Chatbot not found")
        
    conv = await get_or_create_conversation(db, payload.session_id, payload.chatbot_id)
    history = await recent_history(db, conv.id)
    
    await add_message(db, conv.id, "user", payload.message)
    
    # Run orchestration with chatbot context
    result = await run_orchestration(
        payload.message, 
        history, 
        db, 
        chatbot_id=payload.chatbot_id,
        domain=chatbot.domain,
        profile=chatbot.behavior_profile
    )
    
    await add_message(
        db,
        conv.id,
        "assistant",
        result["answer"],
        citations=result.get("citations", {}),
        confidence=result.get("confidence", 1.0)
    )
    
    return result

@api_router.get("/chat/history/{session_id}")
async def chat_history(session_id: str, db: AsyncSession = Depends(get_db)):
    conv = (await db.execute(select(Conversation).where(Conversation.session_id == session_id))).scalar_one_or_none()
    if not conv:
        return []
    return await get_all_history(db, conv.id)

# --- Admin ---

@api_router.get("/admin/stats")
async def admin_stats(db: AsyncSession = Depends(get_db)):
    chatbot_count = (await db.execute(select(func.count(Chatbot.id)))).scalar()
    doc_count = (await db.execute(select(func.count(UploadedDocument.id)))).scalar()
    msg_count = (await db.execute(select(func.count(Message.id)))).scalar()
    
    return {
        "total_chatbots": chatbot_count,
        "total_documents": doc_count,
        "total_messages": msg_count,
        "system_status": "operational"
    }
