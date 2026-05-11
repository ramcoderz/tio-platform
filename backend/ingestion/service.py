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

async def ingest_website(chatbot_id: int, url: str):
    """Background task to ingest website content."""
    from backend.db.session import SessionLocal
    async with SessionLocal() as db:
        try:
            chatbot = await db.get(Chatbot, chatbot_id)
            if not chatbot: return
            
            chatbot.status = "ingesting"
            await db.commit()
            
            # Discover pages
            pages = await scraper.discover_pages(url, limit=settings.top_k * 2) # Use settings for limit
            
            all_text = ""
            for page_url in pages:
                # Deduplication check
                page_stmt = select(UploadedDocument).where(
                    UploadedDocument.chatbot_id == chatbot_id,
                    UploadedDocument.source_path == page_url
                )
                existing_page = (await db.execute(page_stmt)).scalar_one_or_none()
                if existing_page:
                    logger.info(f"Skipping already ingested page: {page_url}")
                    continue

                content = await scraper.extract_content(page_url)
                if not content: continue
                
                all_text += content + "\n\n"
                chunks = _chunk_text(content, page_url, chatbot_id)
                if not chunks: continue
                
                # Index in vector store
                await asyncio.to_thread(upsert_chunks, chunks)
                
                # Persist pseudo-document for the page
                doc = UploadedDocument(
                    chatbot_id=chatbot_id,
                    filename=page_url.split('/')[-1] or "index",
                    source_path=page_url,
                    content_type="text/html"
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
            
            # Domain detection & Profile activation
            domain = scraper.detect_domain(all_text, url)
            chatbot.domain = domain
            chatbot.behavior_profile = domain # For now, 1:1 mapping
            chatbot.status = "ready"
            
            await db.commit()
            logger.info(f"Finished ingesting {url} for Chatbot {chatbot_id}. Detected domain: {domain}")
            
        except Exception as e:
            logger.error(f"Website ingestion failed for {url}: {e}")
            chatbot = await db.get(Chatbot, chatbot_id)
            if chatbot:
                chatbot.status = "error"
                await db.commit()
