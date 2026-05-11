from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
import httpx
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from backend.db.session import get_db
from backend.ingestion.service import ingest_file
from backend.memory.service import conversation, add_message, recent_history, clear_session_state, get_all_history
from backend.agents.orchestrator_agent import clear_session_response_cache, run_orchestration
import os
from backend.models.entities import AgentWorkflow, UploadedDocument, EmbeddingMetadata, SessionMemory, ChatbotProject, Conversation, Message, SystemConfig
from backend.vectorstore.service import vector_count, delete_session_vectors, get_stats, purge_all
import asyncio
from backend.config.settings import get_settings
from backend.api.auth import router as auth_router
from backend.api.audit import router as audit_router
from backend.api.tasks import router as tasks_router

settings = get_settings()

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(audit_router)
api_router.include_router(tasks_router)


class ChatReq(BaseModel):
    session_id: str
    message: str


class WorkflowReq(BaseModel):
    project_id: int
    spec: dict


class ProjectReq(BaseModel):
    name: str


@api_router.post("/documents/upload")
async def upload(file: UploadFile = File(...), session_id: str | None = None, db: AsyncSession = Depends(get_db)):
    return await ingest_file(file, db, session_id=session_id)


@api_router.post("/chat")
async def chat(payload: ChatReq, db: AsyncSession = Depends(get_db)):
    conv = await conversation(db, payload.session_id)
    history = await recent_history(db, conv.id)
    await add_message(db, conv.id, "user", payload.message, {}, 0.0)
    result = await run_orchestration(payload.message, history, db, session_id=payload.session_id)
    await add_message(
        db,
        conv.id,
        "assistant",
        result["answer"],
        {"sources": result["citations"]},
        float(result["confidence"]),
    )
    if result["needs_clarification"]:
        result["answer"] += "\n\nI need a clarification to improve accuracy."
    return result


@api_router.delete("/chat/session/{session_id}")
async def end_chat_session(session_id: str, db: AsyncSession = Depends(get_db)):
    chunk_ids = delete_session_vectors(session_id)
    await clear_session_state(db, session_id, chunk_ids)
    clear_session_response_cache(session_id)
    return {"session_id": session_id, "deleted_chunks": len(chunk_ids)}


@api_router.post("/workflows")
async def create_workflow(payload: WorkflowReq, db: AsyncSession = Depends(get_db)):
    wf = AgentWorkflow(project_id=payload.project_id, spec=payload.spec)
    db.add(wf)
    await db.commit()
    await db.refresh(wf)
    return {"id": wf.id, "project_id": wf.project_id, "spec": wf.spec}


@api_router.post("/projects")
async def create_project(payload: ProjectReq, db: AsyncSession = Depends(get_db)):
    project = ChatbotProject(name=payload.name, config={})
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return {"id": project.id, "name": project.name}

@api_router.get("/chat/sessions")
async def list_chat_sessions(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Conversation))).scalars().all()
    return [{"session_id": r.session_id, "created_at": r.created_at.isoformat()} for r in rows]


@api_router.get("/chat/history/{session_id}")
async def chat_history(session_id: str, db: AsyncSession = Depends(get_db)):
    conv = await conversation(db, session_id)
    return await get_all_history(db, conv.id)


@api_router.get("/admin/activity")
async def get_activity():
    from backend.utils.cache import semantic_cache
    return await semantic_cache.get_activity_feed()


@api_router.get("/admin/streaming")
async def get_streaming_status():
    from backend.utils.cache import semantic_cache
    # Note: In a real app we'd scan keys, but for this demo 
    # we'll return a placeholder or handle it in HybridCache
    return {"status": "operational"}

@api_router.get("/memory/{session_id}")
async def memory(session_id: str, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(SessionMemory).where(SessionMemory.session_id == session_id))).scalars().all()
    return [{"key": r.key, "value": r.value} for r in rows]


@api_router.get("/dashboard")
async def dashboard(db: AsyncSession = Depends(get_db)):
    docs = (await db.execute(select(func.count(UploadedDocument.id)))).scalar_one()
    chunks = (await db.execute(select(func.count(EmbeddingMetadata.id)))).scalar_one()
    return {
        "total_chunks": int(chunks),
        "vector_db_size": vector_count(),
        "active_agents": ["retrieval", "query_refinement", "reasoning", "validation", "memory", "orchestrator"],
        "memory_usage": 0,
        "uploaded_documents": int(docs),
        "inference_latency_ms": 0.0,
        "retrieval_stats": {"top_k": 5, "index": "faiss/chroma"},
    }


@api_router.get("/providers/status")
async def providers_status():
    ollama_ok = False
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{settings.ollama_url}/api/tags")
            ollama_ok = response.status_code == 200
    except Exception:
        ollama_ok = False
    return {
        "active_provider": settings.llm_provider,
        "ollama_url": settings.ollama_url,
        "ollama_model": settings.ollama_model,
        "ollama_ok": ollama_ok,
        "gemini_configured": bool(settings.gemini_api_key),
        "gemini_model": settings.gemini_model,
        "openrouter_configured": bool(settings.openrouter_api_key),
        "openrouter_model": settings.openrouter_model,
    }


@api_router.get("/documents/session/{session_id}")
async def session_documents(session_id: str, db: AsyncSession = Depends(get_db)):
    # Get document IDs from session memory
    doc_ids = (await db.execute(
        select(SessionMemory.value).where(SessionMemory.session_id == session_id, SessionMemory.key == "uploaded_document_id")
    )).scalars().all()
    if not doc_ids:
        return []
    
    ids = [int(did) for did in doc_ids if did.isdigit()]
    docs = (await db.execute(select(UploadedDocument).where(UploadedDocument.id.in_(ids)))).scalars().all()
    
    # Pre-fetch chunk counts for better performance
    chunk_counts = {}
    for d in docs:
        c_count = (await db.execute(select(func.count(EmbeddingMetadata.id)).where(EmbeddingMetadata.document_id == d.id))).scalar()
        chunk_counts[d.id] = c_count

    return [{
        "document_id": d.id, 
        "name": d.filename,
        "summary": d.summary,
        "intel_report": d.intel_report,
        "type": d.content_type,
        "size": os.path.getsize(d.source_path) if os.path.exists(d.source_path) else 0,
        "chunks": chunk_counts.get(d.id, 0),
        "created_at": d.created_at.isoformat()
    } for d in docs]


@api_router.get("/debug/vectorstore")
async def debug_vectorstore():
    """Diagnostic endpoint — shows how many chunks are retrievable right now."""
    from backend.vectorstore.service import _rows, _faiss, _chroma
    chroma_count = 0
    try:
        chroma_count = _chroma.count()
    except Exception:
        pass
    previews = [
        {"chunk_id": r["chunk_id"], "document": r.get("document", ""), "text_preview": r["text"][:120]}
        for r in _rows[:3]
    ]
    return {
        "faiss_in_memory_rows": len(_rows),
        "faiss_index_size": int(_faiss.ntotal),
        "chroma_persisted_chunks": chroma_count,
        "status": "ok" if _rows else "EMPTY — no documents indexed yet",
        "sample_chunks": previews,
    }

@api_router.get("/admin/stats")
async def admin_stats(db: AsyncSession = Depends(get_db)):
    v_stats = get_stats()
    doc_count = (await db.execute(select(func.count(UploadedDocument.id)))).scalar()
    msg_count = (await db.execute(select(func.count(Message.id)))).scalar()
    session_count = (await db.execute(select(func.count(Conversation.id)))).scalar()
    
    return {
        "vectors": v_stats,
        "database": {
            "documents": doc_count,
            "messages": msg_count,
            "sessions": session_count
        },
        "system": {
            "model": settings.ollama_model,
            "url": settings.ollama_url
        }
    }

@api_router.post("/admin/cleanup/all")
async def admin_cleanup_all(db: AsyncSession = Depends(get_db)):
    purge_all()
    await db.execute(delete(Message))
    await db.execute(delete(Conversation))
    await db.execute(delete(UploadedDocument))
    await db.commit()
    return {"status": "Global purge complete"}

@api_router.post("/admin/cleanup/session/{session_id}")
async def admin_cleanup_session(session_id: str, db: AsyncSession = Depends(get_db)):
    delete_session_vectors(session_id)
    clear_session_response_cache(session_id)
    
    conv = (await db.execute(select(Conversation).where(Conversation.session_id == session_id))).scalar_one_or_none()
    if conv:
        await db.execute(delete(Message).where(Message.conversation_id == conv.id))
        await db.execute(delete(Conversation).where(Conversation.id == conv.id))
        await db.commit()
    return {"status": f"Session {session_id} purged"}

@api_router.get("/admin/documents")
async def admin_list_documents(db: AsyncSession = Depends(get_db)):
    stmt = select(UploadedDocument).order_by(UploadedDocument.created_at.desc())
    docs = (await db.execute(stmt)).scalars().all()
    return [{
        "id": d.id, 
        "filename": d.filename, 
        "size": os.path.getsize(d.source_path) if os.path.exists(d.source_path) else 0,
        "created_at": d.created_at.isoformat(),
        "type": d.content_type
    } for d in docs]

@api_router.delete("/admin/documents/{doc_id}")
async def admin_delete_document(doc_id: int, db: AsyncSession = Depends(get_db)):
    doc = await db.get(UploadedDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    from backend.vectorstore.service import delete_chunk_vectors
    chunks_stmt = select(EmbeddingMetadata.chunk_id).where(EmbeddingMetadata.document_id == doc.id)
    chunk_ids = (await db.execute(chunks_stmt)).scalars().all()
    
    if chunk_ids:
        await asyncio.to_thread(delete_chunk_vectors, list(chunk_ids))
    
    await db.execute(delete(EmbeddingMetadata).where(EmbeddingMetadata.document_id == doc.id))
    if os.path.exists(doc.source_path):
        os.remove(doc.source_path)
    
    await db.delete(doc)
    await db.commit()
    return {"status": "success", "message": f"Deleted {doc.filename}"}

@api_router.get("/admin/config/{key}")
async def admin_get_config(key: str, db: AsyncSession = Depends(get_db)):
    config = (await db.execute(select(SystemConfig).where(SystemConfig.key == key))).scalar_one_or_none()
    return {"key": key, "value": config.value if config else None}

@api_router.post("/admin/config")
async def admin_set_config(payload: dict, db: AsyncSession = Depends(get_db)):
    key = payload.get("key")
    value = str(payload.get("value"))
    if not key: return {"error": "Key required"}
    
    config = (await db.execute(select(SystemConfig).where(SystemConfig.key == key))).scalar_one_or_none()
    if config:
        config.value = value
    else:
        db.add(SystemConfig(key=key, value=value))
    await db.commit()
    return {"status": "success", "key": key, "value": value}

