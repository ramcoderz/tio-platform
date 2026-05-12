"""
Ingestion service — file parsing, section-aware chunking, and website ingestion.

Chunk strategy:
  - Target: 400–700 tokens (~1600–2800 chars at ~4 chars/token)
  - Overlap: 80 tokens (~320 chars)
  - Section-aware: splits preferentially at paragraph/heading boundaries
"""

import asyncio
import hashlib
import logging
import re
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from pypdf import PdfReader
from docx import Document as DocxDocument
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from backend.config.settings import get_settings
from backend.models.entities import Chatbot, EmbeddingMetadata, UploadedDocument
from backend.vectorstore.service import upsert_chunks
from backend.ingestion.scraper import scraper

settings = get_settings()

# Chunking constants (chars, ~4 chars per token)
_CHUNK_TARGET = 2200   # ~550 tokens
_CHUNK_MAX    = 2800   # ~700 tokens
_CHUNK_OVERLAP = 320   # ~80 tokens


# ---------------------------------------------------------------------------
# File Parsing
# ---------------------------------------------------------------------------

def _parse_file(path: Path) -> str:
    """Extract raw text from a supported file type."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "\n".join(
            (p.extract_text() or "") for p in PdfReader(str(path)).pages
        )
    if suffix == ".docx":
        return "\n".join(p.text for p in DocxDocument(str(path)).paragraphs)
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    raise ValueError(f"Unsupported format: {suffix}")


# ---------------------------------------------------------------------------
# Section-Aware Chunking
# ---------------------------------------------------------------------------

def _split_into_sections(text: str) -> list[str]:
    """
    Split text at natural boundaries: blank lines, markdown headings,
    or HTML block tags. Falls back to raw text if no boundaries found.
    """
    # Normalise line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Try splitting on double newlines (paragraphs) first
    paragraphs = re.split(r"\n\s*\n", text)
    if len(paragraphs) > 1:
        return [p.strip() for p in paragraphs if p.strip()]

    # Fall back to single newlines
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    return lines


def _extract_entities(text: str) -> list[str]:
    """
    Simple entity extractor for metadata boosting.
    Looks for sequences of Title Case words (Proper Nouns).
    """
    # Pattern for 2+ Title Case words (e.g. Louvre Museum) or specific acronyms (e.g. UNESCO)
    patterns = [
        r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b',
        r'\b[A-Z]{2,}\b',
    ]
    found = []
    for p in patterns:
        found.extend(re.findall(p, text))
    return list(set(found))


def _chunk_text(text: str, source: str, chatbot_id: int) -> list[dict]:
    """
    Section-aware chunking with entity extraction.
    """
    sections = _split_into_sections(text)
    chunks: list[dict] = []
    buffer = ""

    def _flush(buf: str) -> None:
        buf = buf.strip()
        if len(buf) < 50:  # skip very short fragments
            return
        
        entities = _extract_entities(buf)
        chunks.append({
            "chunk_id": str(uuid4()),
            "text": buf,
            "document": source,
            "metadata": {
                "char_start": text.find(buf[:40]) if buf[:40] in text else 0,
                "chatbot_id": chatbot_id,
                "source": source,
                "entities": entities,  # Store extracted entities for boosting
            },
        })

    for section in sections:
        if not section:
            continue

        # If adding this section would exceed the hard max, flush first
        if buffer and len(buffer) + len(section) + 1 > _CHUNK_MAX:
            _flush(buffer)
            # Carry overlap from end of flushed buffer
            buffer = buffer[-_CHUNK_OVERLAP:].lstrip() if len(buffer) > _CHUNK_OVERLAP else ""

        buffer = (buffer + "\n\n" + section).strip() if buffer else section

        # Flush when we've hit the target size
        if len(buffer) >= _CHUNK_TARGET:
            _flush(buffer)
            buffer = buffer[-_CHUNK_OVERLAP:].lstrip() if len(buffer) > _CHUNK_OVERLAP else ""

    # Flush any remaining content
    if buffer:
        _flush(buffer)

    logger.info(f"[CHUNKING] {source!r} → {len(chunks)} chunks (total chars: {len(text)})")
    return chunks


# ---------------------------------------------------------------------------
# File Upload Ingestion
# ---------------------------------------------------------------------------

async def ingest_file(chatbot_id: int, file: UploadFile, db: AsyncSession) -> dict:
    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()

    # Dedup check
    existing = await db.execute(
        select(UploadedDocument).where(
            UploadedDocument.chatbot_id == chatbot_id,
            UploadedDocument.file_hash == file_hash,
        )
    )
    if existing.scalar_one_or_none():
        return {"status": "exists", "message": "File already exists for this chatbot."}

    path = Path(settings.upload_dir) / f"{uuid4()}_{file.filename}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)

    try:
        text = await asyncio.to_thread(_parse_file, path)
        chunks = _chunk_text(text, file.filename, chatbot_id)
        if not chunks:
            raise ValueError("No readable text found in file.")

        await asyncio.to_thread(upsert_chunks, chunks)

        doc = UploadedDocument(
            chatbot_id=chatbot_id,
            filename=file.filename,
            source_path=str(path),
            content_type=file.content_type or "",
            file_hash=file_hash,
        )
        db.add(doc)
        await db.flush()

        for c in chunks:
            db.add(EmbeddingMetadata(
                document_id=doc.id,
                chunk_id=c["chunk_id"],
                text=c["text"],
                metadata_json=c["metadata"],
            ))

        await db.commit()
        return {"document_id": doc.id, "chunks": len(chunks)}

    except Exception as e:
        if path.exists():
            path.unlink()
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Secure Document Download (for linked PDFs/DOCX from websites)
# ---------------------------------------------------------------------------

async def download_document(url: str) -> Path | None:
    import httpx
    import tempfile
    from urllib.parse import urlparse as _urlparse

    MAX_SIZE = 25 * 1024 * 1024  # 25 MB
    ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            head = await client.head(url)
            size = int(head.headers.get("content-length", 0))
            if size > MAX_SIZE:
                logger.warning(f"[DOWNLOAD] File too large ({size} bytes): {url}")
                return None

            ext = Path(_urlparse(url).path).suffix.lower()
            if ext not in ALLOWED_EXTENSIONS:
                logger.warning(f"[DOWNLOAD] Blocked extension {ext!r}: {url}")
                return None

            resp = await client.get(url)
            resp.raise_for_status()

            temp_dir = Path(tempfile.gettempdir()) / "tio_ingestion"
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_path = temp_dir / f"{uuid4()}{ext}"
            temp_path.write_bytes(resp.content)
            return temp_path

    except Exception as e:
        logger.error(f"[DOWNLOAD] Failed for {url}: {e}")
        return None


# ---------------------------------------------------------------------------
# Website Ingestion (background task)
# ---------------------------------------------------------------------------

async def ingest_website(chatbot_id: int, url: str) -> None:
    """
    Background task: crawl website, parse pages and linked docs,
    chunk and index everything, then run domain detection.
    """
    from backend.db.session import SessionLocal

    async with SessionLocal() as db:
        try:
            chatbot = await db.get(Chatbot, chatbot_id)
            if not chatbot:
                return

            chatbot.status = "ingesting"
            await db.commit()
            logger.info(f"[INGESTION] Starting website ingestion for chatbot={chatbot_id}, url={url}")

            # Determine crawl depth based on site type
            is_deep = any(k in url.lower() for k in [
                ".edu", "university", "college", "tourism", "hospital", "clinic"
            ])
            depth = 2 if is_deep else 1
            pages, docs = await scraper.discover_assets(
                url, limit=settings.top_k * 4, depth=depth
            )
            logger.info(f"[INGESTION] Discovered {len(pages)} pages, {len(docs)} docs")

            all_text = ""

            # --- HTML pages ---
            for page_url in pages:
                existing = (await db.execute(
                    select(UploadedDocument).where(
                        UploadedDocument.chatbot_id == chatbot_id,
                        UploadedDocument.source_path == page_url,
                    )
                )).scalar_one_or_none()
                if existing:
                    continue

                content = await scraper.extract_content(page_url)
                if not content:
                    continue

                all_text += content + "\n\n"
                chunks = _chunk_text(content, page_url, chatbot_id)
                if not chunks:
                    continue

                await asyncio.to_thread(upsert_chunks, chunks)

                doc = UploadedDocument(
                    chatbot_id=chatbot_id,
                    filename=page_url.split("/")[-1] or "index",
                    source_path=page_url,
                    content_type="text/html",
                )
                db.add(doc)
                await db.flush()
                for c in chunks:
                    db.add(EmbeddingMetadata(
                        document_id=doc.id,
                        chunk_id=c["chunk_id"],
                        text=c["text"],
                        metadata_json=c["metadata"],
                    ))

            # --- Linked documents ---
            for doc_url in docs:
                existing = (await db.execute(
                    select(UploadedDocument).where(
                        UploadedDocument.chatbot_id == chatbot_id,
                        UploadedDocument.source_path == doc_url,
                    )
                )).scalar_one_or_none()
                if existing:
                    continue

                temp_path = await download_document(doc_url)
                if not temp_path:
                    continue

                try:
                    content = await asyncio.to_thread(_parse_file, temp_path)
                    if not content:
                        continue

                    all_text += content + "\n\n"
                    chunks = _chunk_text(content, doc_url, chatbot_id)
                    if not chunks:
                        continue

                    await asyncio.to_thread(upsert_chunks, chunks)

                    doc = UploadedDocument(
                        chatbot_id=chatbot_id,
                        filename=Path(doc_url).name or "document",
                        source_path=doc_url,
                        content_type=(
                            "application/pdf" if doc_url.endswith(".pdf")
                            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        ),
                    )
                    db.add(doc)
                    await db.flush()
                    for c in chunks:
                        db.add(EmbeddingMetadata(
                            document_id=doc.id,
                            chunk_id=c["chunk_id"],
                            text=c["text"],
                            metadata_json=c["metadata"],
                        ))
                finally:
                    if temp_path.exists():
                        temp_path.unlink()

            # --- Domain detection ---
            from backend.utils.domain_intelligence import domain_detector
            domain = domain_detector.detect(all_text, {"url": url})
            chatbot.domain = domain
            chatbot.behavior_profile = domain
            chatbot.status = "ready"
            await db.commit()

            logger.info(
                f"[INGESTION] Complete — chatbot={chatbot_id}, domain={domain}, "
                f"pages={len(pages)}, docs={len(docs)}"
            )

        except Exception as e:
            logger.error(f"[INGESTION] Failed for chatbot={chatbot_id}: {e}", exc_info=True)
            chatbot = await db.get(Chatbot, chatbot_id)
            if chatbot:
                chatbot.status = "error"
                await db.commit()
