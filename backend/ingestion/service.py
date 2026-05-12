import asyncio
from pathlib import Path
from uuid import uuid4
import re
from pypdf import PdfReader
from docx import Document as DocxDocument
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
import hashlib
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

from backend.config.settings import get_settings
from backend.models.entities import Chatbot, UploadedDocument, EmbeddingMetadata
from backend.vectorstore.service import upsert_chunks
from backend.ingestion.scraper import scraper

settings = get_settings()

def _parse_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)
    if suffix == ".docx":
        return "\n".join(p.text for p in DocxDocument(str(path)).paragraphs)
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    raise ValueError(f"Unsupported format: {suffix}")

def _chunk_text(text: str, source: str, chatbot_id: int) -> list[dict]:
    text = re.sub(r"\s+", " ", text).strip()
    chunks = []
    i = 0
    while i < len(text):
        end = min(i + settings.chunk_size, len(text))
        chunks.append({
            "chunk_id": str(uuid4()),
            "text": text[i:end],
            "document": source,
            "metadata": {"start": i, "end": end, "chatbot_id": chatbot_id}
        })
        if end == len(text): break
        i = end - settings.chunk_overlap
    return chunks

async def ingest_file(chatbot_id: int, file: UploadFile, db: AsyncSession) -> dict:
    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()
    
    # Check for duplicate in this chatbot
    existing = await db.execute(select(UploadedDocument).where(
        UploadedDocument.chatbot_id == chatbot_id, 
        UploadedDocument.file_hash == file_hash
    ))
    if existing.scalar_one_or_none():
        return {"status": "exists", "message": "File already exists for this chatbot."}

    path = Path(settings.upload_dir) / f"{uuid4()}_{file.filename}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    
    try:
        text = await asyncio.to_thread(_parse_file, path)
        chunks = _chunk_text(text, file.filename, chatbot_id)
        if not chunks:
            raise ValueError("No readable text found.")
        
        # Index in vector store
        await asyncio.to_thread(upsert_chunks, chunks)
        
        # Persist in DB
        doc = UploadedDocument(
            chatbot_id=chatbot_id,
            filename=file.filename,
            source_path=str(path),
            content_type=file.content_type or "",
            file_hash=file_hash
        )
        db.add(doc)
        await db.flush()
        
        for c in chunks:
            db.add(EmbeddingMetadata(
                document_id=doc.id,
                chunk_id=c["chunk_id"],
                text=c["text"],
                metadata_json=c["metadata"]
            ))
        
        await db.commit()
        return {"document_id": doc.id, "chunks": len(chunks)}
        
    except Exception as e:
        if path.exists(): path.unlink()
        raise HTTPException(status_code=400, detail=str(e))

async def download_document(url: str) -> Path | None:
    """Safely download a document with security checks."""
    import httpx
    import tempfile
    
    # 1. Validation & Constraints
    MAX_SIZE = 25 * 1024 * 1024 # 25MB
    ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.txt', '.md'}
    ALLOWED_MIMES = {
        'application/pdf', 
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain', 'text/markdown', 'application/octet-stream' # Some servers serve docs as octet-stream
    }
    
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            # Head request to check size/type
            head = await client.head(url)
            
            # Size Check
            size = int(head.headers.get("content-length", 0))
            if size > MAX_SIZE:
                logger.warning(f"File too large: {url} ({size} bytes)")
                return None
            
            # Type Check
            mime = head.headers.get("content-type", "").split(';')[0].lower()
            ext = Path(urlparse(url).path).suffix.lower()
            
            if ext not in ALLOWED_EXTENSIONS:
                logger.warning(f"Blocked extension: {ext} for {url}")
                return None
                
            # Actual Download
            resp = await client.get(url)
            resp.raise_for_status()
            
            # Isolated temp folder
            temp_dir = Path(tempfile.gettempdir()) / "tio_ingestion"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            temp_path = temp_dir / f"{uuid4()}{ext}"
            temp_path.write_bytes(resp.content)
            return temp_path
            
    except Exception as e:
        logger.error(f"Download failed for {url}: {e}")
        return None

async def ingest_website(chatbot_id: int, url: str):
    """Background task to ingest website content and linked documents."""
    from backend.db.session import SessionLocal
    async with SessionLocal() as db:
        try:
            chatbot = await db.get(Chatbot, chatbot_id)
            if not chatbot: return
            
            chatbot.status = "ingesting"
            await db.commit()
            
            # Discover assets with adaptive depth
            is_complex = any(k in url.lower() for k in [".edu", "university", "college", "tourism", "wonderland"])
            depth = 2 if is_complex else 1
            pages, docs = await scraper.discover_assets(url, limit=settings.top_k * 4, depth=depth) 
            
            all_text = ""
            
            # 1. Process HTML Pages
            for page_url in pages:
                # Deduplication check
                page_stmt = select(UploadedDocument).where(
                    UploadedDocument.chatbot_id == chatbot_id,
                    UploadedDocument.source_path == page_url
                )
                existing_page = (await db.execute(page_stmt)).scalar_one_or_none()
                if existing_page: continue

                content = await scraper.extract_content(page_url)
                if not content: continue
                
                all_text += content + "\n\n"
                chunks = _chunk_text(content, page_url, chatbot_id)
                if not chunks: continue
                
                await asyncio.to_thread(upsert_chunks, chunks)
                
                doc = UploadedDocument(
                    chatbot_id=chatbot_id,
                    filename=page_url.split('/')[-1] or "index",
                    source_path=page_url,
                    content_type="text/html"
                )
                db.add(doc)
                await db.flush()
                
                for c in chunks:
                    db.add(EmbeddingMetadata(document_id=doc.id, chunk_id=c["chunk_id"], text=c["text"], metadata_json=c["metadata"]))
            
            # 2. Process Linked Documents
            for doc_url in docs:
                # Deduplication check
                doc_stmt = select(UploadedDocument).where(
                    UploadedDocument.chatbot_id == chatbot_id,
                    UploadedDocument.source_path == doc_url
                )
                existing_doc = (await db.execute(doc_stmt)).scalar_one_or_none()
                if existing_doc: continue

                temp_path = await download_document(doc_url)
                if not temp_path: continue
                
                try:
                    content = await asyncio.to_thread(_parse_file, temp_path)
                    if not content: continue
                    
                    all_text += content + "\n\n"
                    chunks = _chunk_text(content, doc_url, chatbot_id)
                    if not chunks: continue
                    
                    await asyncio.to_thread(upsert_chunks, chunks)
                    
                    # Persist record
                    doc = UploadedDocument(
                        chatbot_id=chatbot_id,
                        filename=Path(doc_url).name or "document",
                        source_path=doc_url,
                        content_type="application/pdf" if doc_url.endswith('.pdf') else "application/msword"
                    )
                    db.add(doc)
                    await db.flush()
                    
                    for c in chunks:
                        db.add(EmbeddingMetadata(document_id=doc.id, chunk_id=c["chunk_id"], text=c["text"], metadata_json=c["metadata"]))
                finally:
                    if temp_path.exists(): temp_path.unlink() # Auto-clean
            
            # Domain detection & Profile activation
            domain = scraper.detect_domain(all_text, url)
            chatbot.domain = domain
            chatbot.behavior_profile = domain
            chatbot.status = "ready"
            
            await db.commit()
            logger.info(f"Finished ingesting {url} for Chatbot {chatbot_id}. Detected domain: {domain}")
            
        except Exception as e:
            logger.error(f"Website ingestion failed for {url}: {e}")
            chatbot = await db.get(Chatbot, chatbot_id)
            if chatbot:
                chatbot.status = "error"
                await db.commit()
