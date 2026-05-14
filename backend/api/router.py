"""
Main API router — all REST endpoints for TiO.

Fixes applied:
  - Task 17: Per-chatbot file delete with full vector chunk cleanup
  - Task 18: Chat history is user + chatbot + session scoped (not just session)
  - Chat POST endpoint passes session_id for proper isolation
"""

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
import os
import asyncio
import httpx

from backend.db.session import get_db
from backend.models.entities import (
    Chatbot, UploadedDocument, Conversation, Message,
    EmbeddingMetadata, SessionMemory, User
)
from backend.api.auth import get_current_user
from backend.memory.service import (
    get_or_create_conversation, add_message, recent_history, get_all_history
)
from backend.ingestion.service import ingest_file, ingest_website
from backend.agents.orchestrator_agent import run_orchestration
from backend.vectorstore.service import delete_chatbot_vectors, delete_chunk_vectors
from backend.config.settings import get_settings

settings = get_settings()
api_router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ChatbotCreate(BaseModel):
    name: str | None = None
    website_url: str | None = None

class ChatReq(BaseModel):
    chatbot_id: int
    session_id: str
    message: str
    user_id: int | None = None   # optional — for user-scoped history


# ---------------------------------------------------------------------------
# Chatbot Management
# ---------------------------------------------------------------------------

@api_router.post("/chatbots")
async def create_chatbot(
    payload: ChatbotCreate, 
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    name = payload.name
    if not name and payload.website_url:
        from urllib.parse import urlparse
        domain_part = urlparse(payload.website_url).netloc
        if domain_part:
            name = domain_part.replace("www.", "").split(".")[0].capitalize() + " Assistant"
        else:
            name = "New Chatbot"

    if payload.website_url:
        try:
            async with httpx.AsyncClient(timeout=5.0, verify=False) as client:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                resp = await client.head(payload.website_url, headers=headers, follow_redirects=True)
                if resp.status_code >= 400 and resp.status_code not in (403, 405):
                    resp_get = await client.get(payload.website_url, headers=headers, follow_redirects=True)
                    if resp_get.status_code >= 400:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Website returned error status: {resp_get.status_code}"
                        )
        except httpx.RequestError as e:
            raise HTTPException(status_code=400, detail=f"Could not reach website: {e}")

    chatbot = Chatbot(
        name=name or "New Chatbot", 
        website_url=payload.website_url, 
        status="pending",
        user_id=user.id
    )
    db.add(chatbot)
    await db.commit()
    await db.refresh(chatbot)

    if payload.website_url:
        asyncio.create_task(ingest_website(chatbot.id, payload.website_url))

    return chatbot


@api_router.get("/chatbots")
async def list_chatbots(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    stmt = select(Chatbot).where(Chatbot.user_id == user.id).order_by(Chatbot.created_at.desc())
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
    from backend.utils.cleanup import deep_delete_chatbot
    await deep_delete_chatbot(chatbot_id, db)
    return {"status": "deleted", "chatbot_id": chatbot_id}


@api_router.delete("/chat/session/{session_id}")
async def delete_session(
    session_id: str, 
    chatbot_id: int = Query(...), 
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Delete a specific session strictly scoped to a chatbot_id and user."""
    stmt = select(Conversation).where(
        Conversation.session_id == session_id,
        Conversation.chatbot_id == chatbot_id,
        Conversation.user_id == user.id
    )
    convs = (await db.execute(stmt)).scalars().all()
    for conv in convs:
        await db.execute(delete(Message).where(Message.conversation_id == conv.id))
        await db.delete(conv)

    # SessionMemory is not explicitly user_id scoped in the schema, but 
    # it belongs to a session_id that we just confirmed is owned by the user.
    if convs:
        await db.execute(delete(SessionMemory).where(
            SessionMemory.session_id == session_id,
            SessionMemory.chatbot_id == chatbot_id
        ))
        await db.commit()
    return {"status": "session_deleted", "session_id": session_id, "chatbot_id": chatbot_id}


# ---------------------------------------------------------------------------
# Ingestion / File Management
# ---------------------------------------------------------------------------

@api_router.post("/chatbots/{chatbot_id}/upload")
async def upload_document(
    chatbot_id: int, 
    file: UploadFile = File(...), 
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    chatbot = await db.get(Chatbot, chatbot_id)
    if not chatbot or chatbot.user_id != user.id:
        raise HTTPException(status_code=404, detail="Chatbot not found or access denied")
    return await ingest_file(chatbot_id, file, db)


@api_router.get("/chatbots/{chatbot_id}/files")
async def list_chatbot_files(
    chatbot_id: int, 
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    chatbot = await db.get(Chatbot, chatbot_id)
    if not chatbot or chatbot.user_id != user.id:
        raise HTTPException(status_code=404, detail="Chatbot not found or access denied")
        
    stmt = select(UploadedDocument).where(UploadedDocument.chatbot_id == chatbot_id)
    docs = (await db.execute(stmt)).scalars().all()
    result = []
    for d in docs:
        chunk_count = await db.scalar(
            select(func.count(EmbeddingMetadata.id)).where(EmbeddingMetadata.document_id == d.id)
        )
        result.append({
            "id": d.id,
            "filename": d.filename,
            "type": d.content_type,
            "source_path": d.source_path,
            "chunks": chunk_count or 0,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        })
    return result


@api_router.delete("/chatbots/{chatbot_id}/files/{doc_id}")
async def delete_chatbot_file(
    chatbot_id: int, 
    doc_id: int, 
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Task 17: Delete a specific file from a chatbot.
    Removes the physical file, its vector chunks, and DB records.
    """
    chatbot = await db.get(Chatbot, chatbot_id)
    if not chatbot or chatbot.user_id != user.id:
        raise HTTPException(status_code=404, detail="Chatbot not found or access denied")
        
    doc = await db.get(UploadedDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.chatbot_id != chatbot_id:
        raise HTTPException(status_code=403, detail="Document does not belong to this chatbot")

    # 1. Get all chunk_ids for this document
    chunk_rows = (await db.execute(
        select(EmbeddingMetadata).where(EmbeddingMetadata.document_id == doc_id)
    )).scalars().all()
    chunk_ids = [c.chunk_id for c in chunk_rows]

    # 2. Delete vectors from FAISS + Chroma
    if chunk_ids:
        await asyncio.to_thread(delete_chunk_vectors, chunk_ids)

    # 3. Delete EmbeddingMetadata rows
    await db.execute(delete(EmbeddingMetadata).where(EmbeddingMetadata.document_id == doc_id))

    # 4. Delete physical file
    if doc.source_path and os.path.exists(doc.source_path):
        try:
            os.remove(doc.source_path)
        except Exception:
            pass

    # 5. Delete DB record
    await db.delete(doc)
    await db.commit()

    return {
        "status": "deleted",
        "doc_id": doc_id,
        "chatbot_id": chatbot_id,
        "chunks_removed": len(chunk_ids),
    }


@api_router.post("/chatbots/{chatbot_id}/reingest")
async def reingest_chatbot(
    chatbot_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    chatbot = await db.get(Chatbot, chatbot_id)
    if not chatbot or chatbot.user_id != user.id:
        raise HTTPException(status_code=404, detail="Chatbot not found or access denied")
    if not chatbot.website_url:
        raise HTTPException(status_code=400, detail="Chatbot has no website URL to re-ingest")

    docs = (await db.execute(
        select(UploadedDocument).where(UploadedDocument.chatbot_id == chatbot_id)
    )).scalars().all()
    for d in docs:
        await db.delete(d)

    await asyncio.to_thread(delete_chatbot_vectors, chatbot_id)

    chatbot.status = "ingesting"
    chatbot.site_profile = None   # clear old profile — will be rebuilt
    await db.commit()

    background_tasks.add_task(ingest_website, chatbot_id, chatbot.website_url)
    return {"status": "reingestion_started"}


# ---------------------------------------------------------------------------
# Chat  (Task 18: user-scoped history)
# ---------------------------------------------------------------------------

@api_router.post("/chat")
async def chat(
    payload: ChatReq, 
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    chatbot = await db.get(Chatbot, payload.chatbot_id)
    if not chatbot or chatbot.user_id != user.id:
        raise HTTPException(status_code=404, detail="Chatbot not found or access denied")

    # Conversation is scoped to session_id + chatbot_id + user_id
    conv = await get_or_create_conversation(
        db, payload.session_id, payload.chatbot_id, user_id=user.id
    )
    history = await recent_history(db, conv.id)
    await add_message(db, conv.id, "user", payload.message)

    result = await run_orchestration(
        payload.message,
        history,
        db,
        chatbot_id=payload.chatbot_id,
        session_id=payload.session_id,
        domain=chatbot.domain,
        profile=chatbot.behavior_profile,
    )

    await add_message(
        db, conv.id, "assistant",
        result["answer"],
        citations=result.get("citations", {}),
        confidence=result.get("confidence", 1.0),
    )
    return result


@api_router.get("/chat/history/{session_id}")
async def chat_history(
    session_id: str,
    chatbot_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Task 18: Chat history strictly scoped to session_id + chatbot_id + user_id.
    """
    stmt = select(Conversation).where(
        Conversation.session_id == session_id,
        Conversation.chatbot_id == chatbot_id,
        Conversation.user_id == user.id
    )

    conv = (await db.execute(stmt.order_by(Conversation.created_at.desc()))).scalars().first()
    if not conv:
        return []
    return await get_all_history(db, conv.id)


@api_router.delete("/chat/history/{session_id}")
async def clear_chat_history(
    session_id: str,
    chatbot_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Clear messages for a specific session+chatbot+user."""
    stmt = select(Conversation).where(
        Conversation.session_id == session_id,
        Conversation.chatbot_id == chatbot_id,
        Conversation.user_id == user.id
    )
    conv = (await db.execute(stmt)).scalar_one_or_none()
    if conv:
        await db.execute(delete(Message).where(Message.conversation_id == conv.id))
        await db.commit()
    return {"status": "cleared", "session_id": session_id, "chatbot_id": chatbot_id}


@api_router.get("/chat/export/{session_id}")
async def export_chat(
    session_id: str,
    format: str = Query("md", enum=["md", "pdf", "docx"]),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Export chat history for a specific session.
    """
    from backend.utils.export import ExportService
    from fastapi.responses import Response

    stmt = select(Conversation).where(
        Conversation.session_id == session_id,
        Conversation.user_id == user.id
    )
    conv = (await db.execute(stmt)).scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = await get_all_history(db, conv.id)
    
    filename = f"tio-chat-{session_id[:8]}.{format}"
    
    if format == "md":
        content = ExportService.to_markdown(messages, session_id)
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return Response(content=content, media_type="text/markdown", headers=headers)
    elif format == "pdf":
        content = ExportService.to_pdf(messages, session_id)
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return Response(content=content, media_type="application/pdf", headers=headers)
    elif format == "docx":
        content = ExportService.to_docx(messages, session_id)
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return Response(content=content, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers=headers)
    
    raise HTTPException(status_code=400, detail="Unsupported format")


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------

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
    query = payload.args.get("query", "general information")
    chunks = await async_retrieve(query, top_k=5, chatbot_id=payload.chatbot_id)
    context = "\n".join([c.text for c in chunks])

    skill_map = {
        "tourism_planner":      ("backend.agents.specialized_agents", "tourism_planner_skill",      lambda: (chatbot.name, context)),
        "attraction_recommender":("backend.agents.specialized_agents", "tourism_planner_skill",     lambda: (query, context)),
        "ride_optimizer":       ("backend.agents.specialized_agents", "ride_optimizer_skill",       lambda: (query, context)),
        "course_finder":        ("backend.agents.specialized_agents", "course_finder_skill",        lambda: (query, context)),
        "admission_assistant":  ("backend.agents.specialized_agents", "admission_assistant_skill",  lambda: (query, context)),
        "scholarship_helper":   ("backend.agents.specialized_agents", "scholarship_helper_skill",   lambda: (query, context)),
        "dept_navigator":       ("backend.agents.specialized_agents", "dept_navigator_skill",       lambda: (query, context)),
        "appointment_guidance": ("backend.agents.specialized_agents", "appointment_guidance_skill", lambda: (query, context)),
        "insurance_assistant":  ("backend.agents.specialized_agents", "insurance_assistant_skill",  lambda: (query, context)),
        "api_assistant":        ("backend.agents.specialized_agents", "api_assistant_skill",        lambda: (query, context)),
        "integration_helper":   ("backend.agents.specialized_agents", "integration_helper_skill",   lambda: (query, context)),
        "sdk_guide":            ("backend.agents.specialized_agents", "sdk_guide_skill",            lambda: (query, context)),
        "shopping_guide":       ("backend.agents.specialized_agents", "shopping_guide_skill",       lambda: (query, context)),
        "doc_summarizer":       ("backend.agents.specialized_agents", "doc_summarizer_skill",       lambda: (context,)),
    }

    from backend.agents.orchestrator_agent import DOMAIN_SKILL_MAP
    domain = chatbot.domain or "general"
    allowed = DOMAIN_SKILL_MAP.get(domain, ["doc_summarizer"])
    if payload.skill_id not in allowed and domain != "general":
        raise HTTPException(
            status_code=400,
            detail=f"Skill '{payload.skill_id}' not permitted for domain '{domain}'"
        )

    if payload.skill_id not in skill_map:
        raise HTTPException(status_code=400, detail=f"Unknown skill: {payload.skill_id}")

    module_path, func_name, args_fn = skill_map[payload.skill_id]
    import importlib
    mod = importlib.import_module(module_path)
    skill_fn = getattr(mod, func_name)
    answer = await skill_fn(*args_fn())

    conv = await get_or_create_conversation(db, payload.session_id, payload.chatbot_id)
    await add_message(db, conv.id, "assistant", answer, citations={"skill": payload.skill_id})
    return {"answer": answer}


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

@api_router.get("/admin/debug/retrieval")
async def debug_retrieval(
    query: str,
    chatbot_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Simulate retrieval for a query and return detailed chunk metadata.
    Helps admins debug why certain content is (or isn't) being found.
    """
    chatbot = await db.get(Chatbot, chatbot_id)
    if not chatbot or (chatbot.user_id and chatbot.user_id != user.id):
        raise HTTPException(status_code=404, detail="Chatbot not found or access denied")

    from backend.vectorstore.service import async_retrieve
    chunks = await async_retrieve(query, top_k=10, chatbot_id=chatbot_id)
    
    return [
        {
            "text": c.text,
            "score": getattr(c, 'score', 0.0),
            "document": c.document,
            "metadata": getattr(c, 'metadata', {})
        }
        for c in chunks
    ]


@api_router.get("/admin/stats")
async def admin_stats(db: AsyncSession = Depends(get_db)):
    return {
        "total_chatbots":      await db.scalar(select(func.count(Chatbot.id))),
        "ready_chatbots":      await db.scalar(select(func.count(Chatbot.id)).where(Chatbot.status == "ready")),
        "total_documents":     await db.scalar(select(func.count(UploadedDocument.id))),
        "total_messages":      await db.scalar(select(func.count(Message.id))),
        "total_conversations": await db.scalar(select(func.count(Conversation.id))),
        "system_status":       "operational",
    }


@api_router.get("/admin/documents")
async def list_all_documents(db: AsyncSession = Depends(get_db)):
    docs = (await db.execute(
        select(UploadedDocument).order_by(UploadedDocument.created_at.desc())
    )).scalars().all()
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "type": d.content_type,
            "chatbot_id": d.chatbot_id,
            "source_path": d.source_path,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]


@api_router.delete("/admin/documents/{doc_id}")
async def delete_document(doc_id: int, db: AsyncSession = Depends(get_db)):
    """Admin: delete any document by ID with full vector + file cleanup."""
    doc = await db.get(UploadedDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete vectors
    chunk_rows = (await db.execute(
        select(EmbeddingMetadata).where(EmbeddingMetadata.document_id == doc_id)
    )).scalars().all()
    chunk_ids = [c.chunk_id for c in chunk_rows]
    if chunk_ids:
        await asyncio.to_thread(delete_chunk_vectors, chunk_ids)
    await db.execute(delete(EmbeddingMetadata).where(EmbeddingMetadata.document_id == doc_id))

    # Delete physical file
    if doc.source_path and os.path.exists(doc.source_path):
        try:
            os.remove(doc.source_path)
        except Exception:
            pass

    await db.delete(doc)
    await db.commit()
    return {"status": "deleted", "doc_id": doc_id, "chunks_removed": len(chunk_ids)}


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
    return {"key": key, "value": cfg.value if cfg else None}


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


@api_router.get("/admin/monitoring")
async def get_monitoring_stats():
    from backend.utils.monitoring import get_stats_snapshot
    return get_stats_snapshot()
