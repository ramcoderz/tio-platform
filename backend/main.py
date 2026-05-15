from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.router import api_router
from backend.api.auth import router as auth_router
from backend.config.settings import get_settings
from backend.db.session import init_db
from backend.websocket.chat_socket import websocket_router
from backend.tasks.document_cleanup import auto_cleanup_worker
from backend.vectorstore.service import initialize_vectorstore
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import logging
from backend.utils.logging_collector import setup_admin_logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
setup_admin_logging()
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting up TiO Backend...")
    try:
        Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
        Path(settings.chroma_dir).mkdir(parents=True, exist_ok=True)
        logger.info(f"Directories verified: {settings.upload_dir}, {settings.chroma_dir}")
        from backend.db.migrate import migrate_db
        await asyncio.to_thread(migrate_db)
        await init_db()
        logger.info("Database migration and initialization successful.")
        
        # Seed starter chatbots
        from backend.db.seed import seed_chatbots
        from backend.db.session import SessionLocal
        async with SessionLocal() as db:
            await seed_chatbots(db)
        
        # Load vector store data
        await asyncio.to_thread(initialize_vectorstore)
        logger.info("Vector store initialized.")
        
        # Preload models
        from backend.rag.embeddings import preload_models
        await asyncio.to_thread(preload_models)
        
        # Start background tasks
        from backend.tasks.refresh_scheduler import start_refresh_scheduler
        from backend.ingestion.worker import ingestion_worker
        await ingestion_worker.start()
        
        asyncio.create_task(auto_cleanup_worker())
        asyncio.create_task(start_refresh_scheduler())
        
        # System health logging task
        async def _health_logger():
            while True:
                await asyncio.sleep(60)
                try:
                    from backend.llm.ollama_client import ollama_client
                    sem = ollama_client.semaphore
                    active_llm = getattr(settings, 'max_concurrent_llm_requests', 2) - sem._value
                    from backend.api.websocket_manager import manager
                    active_ws = sum(len(conns) for conns in manager.active_connections.values())
                    logger.info(f"[HEALTH] Runtime stable. Active WS: {active_ws} | Active LLM reqs: {active_llm}/{getattr(settings, 'max_concurrent_llm_requests', 2)}")
                except Exception as e:
                    logger.warning(f"[HEALTH] Logger error: {e}")
        
        asyncio.create_task(_health_logger())
        
        yield
    finally:
        print("Shutting down TiO Backend...")


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api")
app.include_router(auth_router, prefix="/api/auth")

from backend.api.export import export_router
from backend.api.admin import router as admin_router
app.include_router(export_router, prefix="/api")
app.include_router(admin_router, prefix="/api/internal")

app.include_router(websocket_router)

frontend_dir = Path(__file__).resolve().parents[1] / "frontend"
dist_dir = frontend_dir / "dist"
assets_dir = dist_dir / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/")
async def root() -> FileResponse:
    index_file = dist_dir / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=503, detail="Frontend build not found. Run npm run build in frontend.")
    return FileResponse(index_file, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str) -> FileResponse:
    if full_path.startswith("api"):
        raise HTTPException(status_code=404, detail="Not found")
    index_file = dist_dir / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=503, detail="Frontend build not found. Run npm run build in frontend.")
    return FileResponse(index_file, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
