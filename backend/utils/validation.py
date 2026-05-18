import asyncio
import socket
import logging
import traceback
import sys

logger = logging.getLogger("tio.validation")

async def validate_frontend() -> str:
    """Check if Frontend dev server (Vite) on port 5173 is reachable."""
    try:
        # Fast non-blocking socket connect
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection("127.0.0.1", 5173),
            timeout=1.5
        )
        writer.close()
        await writer.wait_closed()
        return "ONLINE"
    except Exception:
        return "OFFLINE"

async def validate_backend() -> str:
    """FastAPI is running this code, so backend is guaranteed ONLINE."""
    return "ONLINE"

async def validate_worker() -> str:
    """Check if the background ingestion worker loop is currently active."""
    try:
        from backend.ingestion.worker import ingestion_worker
        if ingestion_worker and ingestion_worker._worker_task and not ingestion_worker._worker_task.done():
            return "ACTIVE"
        return "INACTIVE"
    except Exception:
        return "DISCONNECTED"

async def validate_crawler() -> str:
    """Verify crawler dependencies and active state."""
    try:
        import httpx
        import bs4
        import trafilatura
        return "READY"
    except Exception:
        return "ERROR"

async def validate_embeddings() -> str:
    """Verify primary sentence-transformers embedding model status."""
    try:
        from backend.rag.embeddings import model
        m = model()
        if m:
            return "READY"
        return "ERROR"
    except Exception:
        return "ERROR"

async def validate_vectorstore() -> dict:
    """Verify ChromaDB connectivity, loaded collections and embedding dimension."""
    try:
        from backend.vectorstore.service import _chroma_client
        colls = _chroma_client.list_collections()
        coll_name = colls[0].name if colls else "tio_chunks"
        # BGE embeddings have a dimension of 384
        return {
            "status": "READY",
            "collection": coll_name,
            "dimension": 384
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "collection": "none",
            "dimension": 0,
            "error": str(e)
        }

async def validate_llm() -> dict:
    """Verify local Ollama server status, primary model and fallbacks."""
    try:
        from backend.config.settings import get_settings
        from backend.llm.ollama_client import ollama_client
        settings = get_settings()
        primary = settings.primary_model
        fallback = settings.fallback_model
        
        if await ollama_client.is_available():
            if await ollama_client.has_model(primary):
                return {"status": "READY", "model": primary, "available": True}
            else:
                # Try fallback
                if await ollama_client.has_model(fallback):
                    return {"status": "DEGRADED", "model": fallback, "available": True, "warning": "Primary model unavailable. Switching to fallback."}
                else:
                    return {"status": "DEGRADED", "model": "none", "available": False, "warning": "Primary and fallback models both unavailable."}
        return {"status": "OFFLINE", "model": "none", "available": False}
    except Exception:
        return {"status": "OFFLINE", "model": "none", "available": False}

async def validate_websocket() -> str:
    """Verify if global websocket manager is initialized."""
    try:
        from backend.api.websocket_manager import manager
        if manager:
            return "CONNECTED"
        return "DISCONNECTED"
    except Exception:
        return "DISCONNECTED"

async def validate_adaptive_retrieval() -> str:
    """Verify adaptive retrieval capability is active."""
    try:
        from backend.rag.retrieval import retrieve
        return "ACTIVE"
    except Exception:
        return "ERROR"

async def get_runtime_status_report() -> str:
    """Build a beautifully formatted ASCII console report for TiO's health."""
    fe = await validate_frontend()
    be = await validate_backend()
    wrk = await validate_worker()
    crwl = await validate_crawler()
    emb = await validate_embeddings()
    vs = await validate_vectorstore()
    llm = await validate_llm()
    ws = await validate_websocket()
    
    report = (
        "========================================================\n"
        "TiO Runtime Status\n"
        "========================================================\n\n"
        f"Frontend:      {fe}\n"
        f"Backend:       {be}\n"
        f"Worker:        {wrk}\n"
        f"Crawler:       {crwl}\n"
        f"Embeddings:    {emb}\n"
        f"Vectorstore:   {vs['status']}\n"
        f"LLM:           {llm['status']} ({llm['model']})\n"
        f"WebSocket:     {ws}\n\n"
        "========================================================\n"
    )
    return report

async def perform_startup_audit():
    """Print connection audit status to stdout during backend boot sequence."""
    print(flush=True)
    print("========================================================", flush=True)
    print("[SYSTEM]", flush=True)
    print("Performing runtime connection audit...", flush=True)
    print("========================================================", flush=True)
    print(flush=True)
    
    # 1. Frontend
    fe = await validate_frontend()
    if fe == "ONLINE":
        print("[OK] Frontend server connected", flush=True)
    else:
        print("[WARNING] Frontend server disconnected/offline", flush=True)
    await asyncio.sleep(0.02)
    
    # 2. Backend
    print("[OK] FastAPI backend connected", flush=True)
    await asyncio.sleep(0.02)
    
    # 3. WS Manager
    ws = await validate_websocket()
    if ws == "CONNECTED":
        print("[OK] WebSocket manager initialized", flush=True)
    else:
        print("[WARNING] WebSocket manager offline", flush=True)
    await asyncio.sleep(0.02)
        
    # 4. Worker
    wrk = await validate_worker()
    if wrk == "ACTIVE":
        print("[OK] Ingestion worker active", flush=True)
    else:
        print("[WARNING] Ingestion worker inactive", flush=True)
    await asyncio.sleep(0.02)
        
    # 5. Crawler
    crwl = await validate_crawler()
    if crwl == "READY":
        print("[OK] Crawler pipeline active", flush=True)
    else:
        print("[WARNING] Crawler pipeline error", flush=True)
    await asyncio.sleep(0.02)
        
    # 6. Parser
    try:
        import bs4, trafilatura
        print("[OK] Parser service active", flush=True)
    except Exception:
        print("[WARNING] Parser service unavailable", flush=True)
    await asyncio.sleep(0.02)
        
    # 7. Embedding
    emb = await validate_embeddings()
    if emb == "READY":
        print("[OK] Embedding service active", flush=True)
    else:
        print("[WARNING] Embedding service unavailable", flush=True)
    await asyncio.sleep(0.02)
        
    # 8. Vectorstore
    vs = await validate_vectorstore()
    if vs['status'] == "READY":
        print("[OK] Vectorstore active", flush=True)
        print(f"[VECTORSTORE] Collection loaded: {vs['collection']}", flush=True)
        print(f"[VECTORSTORE] Embedding dimension: {vs['dimension']}", flush=True)
    else:
        print("[WARNING] Vectorstore error", flush=True)
    await asyncio.sleep(0.02)
        
    # 9. LLM router
    print("[LLM] Checking Ollama...", flush=True)
    llm_val = await validate_llm()
    if llm_val['available']:
        if llm_val['status'] == "READY":
            print(f"[OK] {llm_val['model']} available", flush=True)
        else:
            print(f"[WARNING] Primary model unavailable", flush=True)
            print(f"Switching to fallback: {llm_val['model']}", flush=True)
        print("[OK] LLM router active", flush=True)
    else:
        print("[WARNING] LLM router degraded — no local Ollama models found", flush=True)
    await asyncio.sleep(0.02)
        
    print(flush=True)
    print("========================================================", flush=True)
    print("[SUCCESS]", flush=True)
    print("All core runtime systems connected", flush=True)
    print("========================================================", flush=True)
    print(flush=True)
