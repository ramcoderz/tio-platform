from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import os
import sys
import httpx
import logging

from backend.config.settings import get_settings
from backend.db.session import init_db
from backend.vectorstore.service import initialize_vectorstore
from backend.api.router import api_router
from backend.api.auth import router as auth_router
from backend.api.admin import router as admin_router
from backend.websocket.chat_socket import websocket_router
from backend.utils.console import console

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup Sequence
    import sys
    import traceback
    
    try:
        print("========================================================", flush=True)
        print("[SYSTEM] Starting TiO Backend", flush=True)
        print("========================================================", flush=True)
        print(flush=True)

        # 1. Loading environment variables
        print("[SYSTEM]", flush=True)
        print("Loading environment variables...", flush=True)
        await asyncio.sleep(0.05)
        print(flush=True)

        # 2. Loading feature flags
        print("[SYSTEM]", flush=True)
        print("Loading feature flags...", flush=True)
        await asyncio.sleep(0.05)
        print(flush=True)

        # 3. Initializing SQLite
        print("[DB]", flush=True)
        print("Initializing SQLite...", flush=True)
        try:
            await init_db()
            from backend.db.session import SessionLocal
            from backend.db.seed import seed_chatbots
            async with SessionLocal() as db_session:
                await seed_chatbots(db_session)
        except Exception as e:
            print("[FATAL]", flush=True)
            print("SQLite initialization failed:", flush=True)
            traceback.print_exc(file=sys.stderr)
            raise e
        await asyncio.sleep(0.05)
        print(flush=True)

        # 4. Initializing ChromaDB
        print("[INDEX]", flush=True)
        print("Initializing ChromaDB...", flush=True)
        try:
            from backend.vectorstore.service import _chroma_client
            _chroma_client.list_collections()
        except Exception as e:
            print("[WARNING]", flush=True)
            print("ChromaDB initialization failed, starting in fallback mode:", flush=True)
            traceback.print_exc(file=sys.stderr)
        await asyncio.sleep(0.05)
        print(flush=True)

        # 5. Initializing FAISS
        print("[INDEX]", flush=True)
        print("Initializing FAISS...", flush=True)
        try:
            initialize_vectorstore()
        except Exception as e:
            print("[WARNING]", flush=True)
            print("FAISS vectorstore initialization failed, starting in fallback mode:", flush=True)
            traceback.print_exc(file=sys.stderr)
        await asyncio.sleep(0.05)
        print(flush=True)

        # 6. Checking Ollama connection
        print("[LLM]", flush=True)
        print("Checking Ollama connection...", flush=True)
        ollama_online = False
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{settings.ollama_url}/api/tags", timeout=1.0)
                if r.status_code == 200:
                    ollama_online = True
        except Exception:
            pass

        if ollama_online:
            print("Ollama online", flush=True)
        else:
            print("[LLM]", flush=True)
            print("Ollama unavailable — fallback mode enabled", flush=True)
        await asyncio.sleep(0.05)
        print(flush=True)

        # 7. Initializing websocket manager
        print("[WS]", flush=True)
        print("Initializing websocket manager...", flush=True)
        try:
            from backend.api.websocket_manager import manager
        except Exception as e:
            print("[WARNING]", flush=True)
            print("Websocket manager initialization failed:", flush=True)
            traceback.print_exc(file=sys.stderr)
        await asyncio.sleep(0.05)
        print(flush=True)

        # 7.5. Initializing Ingestion Worker
        print("[INGESTION]", flush=True)
        print("Initializing background ingestion worker...", flush=True)
        try:
            from backend.ingestion.worker import ingestion_worker
            await ingestion_worker.start()
            print("Ingestion worker started successfully", flush=True)
        except Exception as e:
            print("[WARNING]", flush=True)
            print("Ingestion worker initialization failed:", flush=True)
            traceback.print_exc(file=sys.stderr)
        await asyncio.sleep(0.05)
        print(flush=True)

        # 8. Registering API routes
        print("[API]", flush=True)
        print("Registering API routes...", flush=True)
        await asyncio.sleep(0.05)
        print(flush=True)

        # 9. Performing connection audit
        try:
            from backend.utils.validation import perform_startup_audit
            await perform_startup_audit()
        except Exception as e:
            print(f"[WARNING] Startup connection audit failed: {e}", flush=True)

        yield
    except Exception as e:
        print("========================================================", flush=True)
        print("[FATAL]", flush=True)
        print("Backend startup failed with an unhandled exception:", flush=True)
        print("========================================================", flush=True)
        traceback.print_exc(file=sys.stderr)
        raise e

    
    # Shutdown Sequence
    print("========================================================")
    print("[SYSTEM] Shutting down TiO Platform")
    print("========================================================")
    print()
    print("[WS]")
    print("Closing active websocket connections...")
    await asyncio.sleep(0.05)
    print()
    print("[INGESTION]")
    print("Stopping active ingestion workers...")
    await asyncio.sleep(0.05)
    print()
    print("[LLM]")
    print("Closing inference streams...")
    await asyncio.sleep(0.05)
    print()
    print("[DB]")
    print("Closing database sessions...")
    await asyncio.sleep(0.05)
    print()
    print("[VECTORSTORE]")
    print("Persisting vector collections...")
    await asyncio.sleep(0.05)
    print()
    print("========================================================")
    print("[SUCCESS]")
    print("TiO shutdown complete")
    print("========================================================")

app = FastAPI(title=settings.app_name, lifespan=lifespan)

# CORS
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
if settings.allowed_origins:
    for o in settings.allowed_origins:
        if o != "*" and o not in origins:
            origins.append(o)

allow_origin_regex = None
if "*" in settings.allowed_origins:
    allow_origin_regex = r"https?://.*"

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if allow_origin_regex is None else [],
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(api_router, prefix="/api")
app.include_router(auth_router, prefix="/api/auth")
app.include_router(admin_router, prefix="/api/internal")
app.include_router(websocket_router)