from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.router import api_router
from backend.config.settings import get_settings
from backend.db.session import init_db
from backend.websocket.chat_socket import websocket_router
from backend.tasks.document_cleanup import auto_cleanup_worker
from backend.vectorstore.service import initialize_vectorstore
import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    print("Starting up TiO Backend...")
    try:
        Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
        Path(settings.chroma_dir).mkdir(parents=True, exist_ok=True)
        print(f"Directories verified: {settings.upload_dir}, {settings.chroma_dir}")
        await init_db()
        print("Database initialized successfully.")
        
        # Load vector store data
        await asyncio.to_thread(initialize_vectorstore)
        print("Vector store initialized.")
        
        # Start background tasks
        asyncio.create_task(auto_cleanup_worker())
        
        yield
    finally:
        print("Shutting down TiO Backend...")


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api")
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
