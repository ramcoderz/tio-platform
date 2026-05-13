from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
import os
import asyncio
import httpx

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
            
    # Validate website URL if provided
    if payload.website_url:
        try:
            async with httpx.AsyncClient(timeout=5.0, verify=False) as client:
                # Add a realistic User-Agent to avoid immediate blocking from some hosts
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                resp = await client.head(payload.website_url, headers=headers, follow_redirects=True)
                if resp.status_code >= 400 and resp.status_code != 403 and resp.status_code != 405:
                    # Fallback to GET if HEAD fails with some specific errors (some servers reject HEAD)
                    resp_get = await client.get(payload.website_url, headers=headers, follow_redirects=True)
                    if resp_get.status_code >= 400:
                        raise HTTPException(status_code=400, detail=f"Website returned error status: {resp_get.status_code}")
        except httpx.RequestError as e:
            raise HTTPException(status_code=400, detail=f"Could not reach website: {str(e)}")
    
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
        if d.source_path and os.path.exists(d.source_path):
            try: os.remove(d.source_path)
            except: pass
    
    # 2. Vector Cleanup
    await asyncio.to_thread(delete_chatbot_vectors, chatbot_id)
    
    # 3. Cache & Memory Cleanup
    await db.execute(delete(SessionMemory).where(SessionMemory.session_id.like(f"%-c{chatbot_id}")))
    
    # 4. Database Cleanup (Cascades will handle Conversations/Messages)
    await db.delete(chatbot)
    await db.commit()
    
    return {"status": "deleted"}

@api_router.delete("/chat/session/{session_id}")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    # 1. Find conversation
    stmt = select(Conversation).where(Conversation.session_id == session_id)
    conv = (await db.execute(stmt)).scalar_one_or_none()
    
    if conv:
        # 2. Delete messages (Cascaded)
        # 3. Delete session memory
        await db.execute(delete(SessionMemory).where(SessionMemory.session_id == session_id))
        
        # 4. Delete conversation
        await db.delete(conv)
        await db.commit()
        
    return {"status": "session_deleted"}

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

@api_router.post("/chatbots/{chatbot_id}/reingest")
async def reingest_chatbot(chatbot_id: int, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    chatbot = await db.get(Chatbot, chatbot_id)
    if not chatbot:
        raise HTTPException(status_code=404, detail="Chatbot not found")
    
    if not chatbot.website_url:
        raise HTTPException(status_code=400, detail="Chatbot has no website URL to re-ingest")

    # 1. Clear existing documents and their chunks (DB)
    stmt = select(UploadedDocument).where(UploadedDocument.chatbot_id == chatbot_id)
    docs = (await db.execute(stmt)).scalars().all()
    for d in docs:
        await db.delete(d)
    
    # 2. Clear vectors
    await asyncio.to_thread(delete_chatbot_vectors, chatbot_id)
    
    # 3. Update status and trigger task
    chatbot.status = "ingesting"
    await db.commit()
    
    background_tasks.add_task(ingest_website, chatbot_id, chatbot.website_url)
    return {"status": "reingestion_started"}


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
async def chat_history(session_id: str, chatbot_id: int | None = None, db: AsyncSession = Depends(get_db)):
    stmt = select(Conversation).where(Conversation.session_id == session_id)
    if chatbot_id:
        stmt = stmt.where(Conversation.chatbot_id == chatbot_id)
    conv = (await db.execute(stmt)).scalars().first()
    if not conv:
        return []
    return await get_all_history(db, conv.id)

class SkillReq(BaseModel):
    skill_id: str
    chatbot_id: int
    session_id: str
    args: dict = {}

@api_router.post("/skills/execute")
async def execute_skill(payload: SkillReq, db: AsyncSession = Depends(get_db)):
    chatbot = await db.get(Chatbot, payload.chatbot_id)
    if not chatbot:
        raise HTTPException(status_code=404, detail="Chatbot not found")
    
    from backend.vectorstore.service import async_retrieve
    
    # Get context from chatbot knowledge
    query = payload.args.get("query", "general information")
    chunks = await async_retrieve(query, top_k=5, chatbot_id=payload.chatbot_id)
    context = "\n".join([c.text for c in chunks])
    
    skill_map = {
        # Tourism
        "tourism_planner": ("backend.agents.specialized_agents", "tourism_planner_skill", lambda: (chatbot.name, context)),
        "attraction_recommender": ("backend.agents.specialized_agents", "tourism_planner_skill", lambda: (query, context)), # Reusing planner for recommender
        "ride_optimizer": ("backend.agents.specialized_agents", "ride_optimizer_skill", lambda: (query, context)),
        
        # Education
        "course_finder": ("backend.agents.specialized_agents", "course_finder_skill", lambda: (query, context)),
        "admission_assistant": ("backend.agents.specialized_agents", "admission_assistant_skill", lambda: (query, context)),
        "scholarship_helper": ("backend.agents.specialized_agents", "scholarship_helper_skill", lambda: (query, context)),
        
        # Medical
        "dept_navigator": ("backend.agents.specialized_agents", "dept_navigator_skill", lambda: (query, context)),
        "appointment_guidance": ("backend.agents.specialized_agents", "appointment_guidance_skill", lambda: (query, context)),
        "insurance_assistant": ("backend.agents.specialized_agents", "insurance_assistant_skill", lambda: (query, context)),
        
        # Developer
        "api_assistant": ("backend.agents.specialized_agents", "api_assistant_skill", lambda: (query, context)),
        "integration_helper": ("backend.agents.specialized_agents", "integration_helper_skill", lambda: (query, context)),
        "sdk_guide": ("backend.agents.specialized_agents", "sdk_guide_skill", lambda: (query, context)),
        
        # Ecommerce
        "shopping_guide": ("backend.agents.specialized_agents", "shopping_guide_skill", lambda: (query, context)),
        
        # General
        "doc_summarizer": ("backend.agents.specialized_agents", "doc_summarizer_skill", lambda: (context,)),
    }
    
    from backend.agents.orchestrator_agent import DOMAIN_SKILL_MAP
    
    # Domain Locking for Skills
    domain = chatbot.domain or "general"
    allowed_skills = DOMAIN_SKILL_MAP.get(domain, ["doc_summarizer"])
    
    if payload.skill_id not in allowed_skills and domain != "general":
        raise HTTPException(
            status_code=400, 
            detail=f"Skill '{payload.skill_id}' is not permitted for domain '{domain}'"
        )

    if payload.skill_id not in skill_map:
        raise HTTPException(status_code=400, detail=f"Unknown skill: {payload.skill_id}")
    
    module_path, func_name, args_fn = skill_map[payload.skill_id]
    
    import importlib
    mod = importlib.import_module(module_path)
    skill_fn = getattr(mod, func_name)
    answer = await skill_fn(*args_fn())
    
    # Save to conversation history
    conv = await get_or_create_conversation(db, payload.session_id, payload.chatbot_id)
    await add_message(db, conv.id, "assistant", answer, citations={"skill": payload.skill_id})
    
    return {"answer": answer}


@api_router.get("/admin/stats")
async def admin_stats(db: AsyncSession = Depends(get_db)):
    chatbot_count   = (await db.execute(select(func.count(Chatbot.id)))).scalar()
    ready_count     = (await db.execute(select(func.count(Chatbot.id)).where(Chatbot.status == "ready"))).scalar()
    doc_count       = (await db.execute(select(func.count(UploadedDocument.id)))).scalar()
    msg_count       = (await db.execute(select(func.count(Message.id)))).scalar()
    conv_count      = (await db.execute(select(func.count(Conversation.id)))).scalar()

    return {
        "total_chatbots":      chatbot_count,
        "ready_chatbots":      ready_count,
        "total_documents":     doc_count,
        "total_messages":      msg_count,
        "total_conversations": conv_count,
        "system_status":       "operational",
    }

@api_router.get("/admin/documents")
async def list_all_documents(db: AsyncSession = Depends(get_db)):
    stmt = select(UploadedDocument).order_by(UploadedDocument.created_at.desc())
    docs = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id":         d.id,
            "filename":   d.filename,
            "type":       d.content_type,
            "chatbot_id": d.chatbot_id,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]

@api_router.delete("/admin/documents/{doc_id}")
async def delete_document(doc_id: int, db: AsyncSession = Depends(get_db)):
    doc = await db.get(UploadedDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.source_path and os.path.exists(doc.source_path):
        try: os.remove(doc.source_path)
        except: pass
    await db.delete(doc)
    await db.commit()
    return {"status": "deleted"}

@api_router.post("/admin/cleanup/all")
async def cleanup_all(db: AsyncSession = Depends(get_db)):
    await db.execute(delete(Message))
    await db.execute(delete(Conversation))
    await db.execute(delete(UploadedDocument))
    await db.commit()
    return {"status": "purged"}

@api_router.get("/admin/config/{key}")
async def get_config(key: str, db: AsyncSession = Depends(get_db)):
    from backend.models.entities import SystemConfig
    cfg = (await db.execute(select(SystemConfig).where(SystemConfig.key == key))).scalar_one_or_none()
    if not cfg:
        return {"key": key, "value": None}
    return {"key": cfg.key, "value": cfg.value}

@api_router.get("/admin/monitoring")
async def get_monitoring_stats():
    from backend.utils.monitoring import get_stats_snapshot
    return get_stats_snapshot()


@api_router.post("/admin/config")
async def set_config(payload: dict, db: AsyncSession = Depends(get_db)):
    from backend.models.entities import SystemConfig
    key = payload.get("key")
    value = str(payload.get("value", ""))
    cfg = (await db.execute(select(SystemConfig).where(SystemConfig.key == key))).scalar_one_or_none()
    if cfg:
        cfg.value = value
    else:
        cfg = SystemConfig(key=key, value=value)
        db.add(cfg)
    await db.commit()
    return {"key": key, "value": value}
