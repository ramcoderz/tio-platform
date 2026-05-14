"""
Ingestion service — file parsing, section-aware chunking, and website ingestion.

Improvements (Priority 4):
  - Deduplication by content hash
  - Boilerplate / navigation filtering
  - Content quality scoring (skip low-value chunks)
  - Site intelligence profile built after ingestion
  - Better domain detection with confidence threshold
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
from backend.utils.entities import extract_entities as robust_extract_entities

settings = get_settings()

# Chunking constants (chars, ~4 chars per token)
_CHUNK_TARGET = 2200   # ~550 tokens
_CHUNK_MAX    = 2800   # ~700 tokens
_CHUNK_OVERLAP = 320   # ~80 tokens

# Quality thresholds
_MIN_CHUNK_CHARS = 80       # skip very short fragments
_MIN_WORD_COUNT  = 15       # skip chunks with fewer words (likely nav/boilerplate)
_MAX_LINK_DENSITY = 0.4     # skip chunks where >40% of words look like URLs/nav


# ---------------------------------------------------------------------------
# Boilerplate detection
# ---------------------------------------------------------------------------

_BOILERPLATE_PATTERNS = [
    r'^(home|about|contact|login|sign up|register|menu|navigation|footer|header|sitemap|privacy policy|terms of service|cookie policy|all rights reserved)$',
    r'^(click here|read more|learn more|view all|see all|show more|load more|back to top)$',
    r'^(\d{4}\s*[©|&copy;])',     # copyright lines
    r'^(follow us|share this|subscribe|newsletter)',
    r'^\s*[\|\-\•\*]\s*$',       # separator-only lines
    r'^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s*:?\s*\d',  # hours lines
]
_BOILERPLATE_RE = [re.compile(p, re.IGNORECASE) for p in _BOILERPLATE_PATTERNS]


def _is_boilerplate(text: str) -> bool:
    t = text.strip().lower()
    if len(t) < 5:
        return True
    for pat in _BOILERPLATE_RE:
        if pat.search(t):
            return True
    return False


def _link_density(text: str) -> float:
    """Ratio of URL-like tokens to total words — high = navigation/boilerplate."""
    words = text.split()
    if not words:
        return 0.0
    url_words = sum(1 for w in words if w.startswith(("http", "www.", "/")) or w.endswith((".html", ".php", ".asp")))
    return url_words / len(words)


def _content_score(text: str) -> float:
    """
    Simple quality score 0–1 for a text chunk:
      - Penalise short chunks
      - Penalise high link density
      - Penalise all-caps content (navigation menus)
      - Reward longer, sentence-like text
    """
    if not text:
        return 0.0
    words = text.split()
    wc = len(words)

    if wc < _MIN_WORD_COUNT:
        return 0.1

    ld = _link_density(text)
    if ld > _MAX_LINK_DENSITY:
        return 0.1

    # Penalise if most words are capitalised (like menu items)
    caps_ratio = sum(1 for w in words if w.isupper() and len(w) > 1) / max(wc, 1)
    if caps_ratio > 0.5:
        return 0.2

    # Reward sentence structure
    sentence_count = len(re.findall(r'[.!?]', text))
    score = min(1.0, 0.3 + (sentence_count * 0.1) + (wc / 200) * 0.4)
    return round(score, 2)


# ---------------------------------------------------------------------------
# File Parsing
# ---------------------------------------------------------------------------

def _parse_file(path: Path) -> str:
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
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = re.split(r"\n\s*\n", text)
    if len(paragraphs) > 1:
        return [p.strip() for p in paragraphs if p.strip()]
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    return lines


def _extract_entities(text: str) -> list[str]:
    """Link to centralized entity extraction."""
    return robust_extract_entities(text)


def _chunk_text(
    text: str,
    source: str,
    chatbot_id: int,
    domain: str = "general",
    source_type: str = "text/html",
) -> list[dict]:
    """Section-aware chunking with quality filtering and entity extraction."""
    sections = _split_into_sections(text)
    chunks: list[dict] = []
    seen_hashes: set[str] = set()
    buffer = ""

    def _flush(buf: str) -> None:
        buf = buf.strip()
        if len(buf) < _MIN_CHUNK_CHARS:
            return

        # Boilerplate filter
        if _is_boilerplate(buf):
            return

        # Content quality filter
        if _content_score(buf) < 0.15:
            return

        # Deduplication by content hash
        h = hashlib.md5(buf.encode()).hexdigest()
        if h in seen_hashes:
            return
        seen_hashes.add(h)

        entities = _extract_entities(buf)
        # Priority: homepage (3) > high-quality docs (2) > others (1)
        priority = 1
        if source == "/" or source.endswith(("index.html", "index.php")) or len(source.split("/")) < 4:
            priority = 3
        elif _content_score(buf) > 0.6:
            priority = 2

        chunks.append({
            "chunk_id": str(uuid4()),
            "text": buf,
            "document": source,
            "metadata": {
                "char_start": text.find(buf[:40]) if buf[:40] in text else 0,
                "chatbot_id": chatbot_id,
                "domain": domain,
                "source": source,
                "source_type": source_type,
                "entities": entities,
                "quality_score": _content_score(buf),
                "priority": priority,
            },
        })

    for section in sections:
        if not section:
            continue

        # Skip individual boilerplate sections before buffering
        if _is_boilerplate(section):
            continue

        if buffer and len(buffer) + len(section) + 1 > _CHUNK_MAX:
            _flush(buffer)
            buffer = buffer[-_CHUNK_OVERLAP:].lstrip() if len(buffer) > _CHUNK_OVERLAP else ""

        buffer = (buffer + "\n\n" + section).strip() if buffer else section

        if len(buffer) >= _CHUNK_TARGET:
            _flush(buffer)
            buffer = buffer[-_CHUNK_OVERLAP:].lstrip() if len(buffer) > _CHUNK_OVERLAP else ""

    if buffer:
        _flush(buffer)

    logger.info(f"[CHUNKING] {source!r} → {len(chunks)} quality chunks from {len(sections)} sections")
    return chunks


# ---------------------------------------------------------------------------
# File Upload Ingestion
# ---------------------------------------------------------------------------

async def ingest_file(chatbot_id: int, file: UploadFile, db: AsyncSession) -> dict:
    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()

    # Dedup check by file hash
    existing = await db.execute(
        select(UploadedDocument).where(
            UploadedDocument.chatbot_id == chatbot_id,
            UploadedDocument.file_hash == file_hash,
        )
    )
    if existing.scalar_one_or_none():
        return {"status": "exists", "message": "File already indexed for this chatbot."}

    path = Path(settings.upload_dir) / f"{uuid4()}_{file.filename}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)

    try:
        text = await asyncio.to_thread(_parse_file, path)
        chatbot = await db.get(Chatbot, chatbot_id)
        domain = chatbot.domain if chatbot else "general"
        chunks = _chunk_text(text, file.filename, chatbot_id, domain=domain)
        if not chunks:
            raise ValueError("No readable text found in file (or all content filtered as boilerplate).")

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
# Secure Document Download
# ---------------------------------------------------------------------------

async def download_document(url: str) -> Path | None:
    import httpx
    import tempfile
    from urllib.parse import urlparse as _urlparse

    MAX_SIZE = 25 * 1024 * 1024
    ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            head = await client.head(url)
            size = int(head.headers.get("content-length", 0))
            if size > MAX_SIZE:
                logger.warning(f"[DOWNLOAD] Too large ({size} bytes): {url}")
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
    Background task: crawl, parse, quality-filter, chunk, index,
    then build a site intelligence profile.
    """
    from backend.db.session import SessionLocal

    async with SessionLocal() as db:
        try:
            chatbot = await db.get(Chatbot, chatbot_id)
            if not chatbot:
                return

            chatbot.status = "ingesting"
            await db.commit()
            logger.info(f"[INGESTION] Starting for chatbot={chatbot_id}, url={url}")

            # --- Early Domain Detection (from homepage) ---
            from backend.utils.domain_intelligence import domain_detector
            homepage_content = await scraper.extract_content(url)

            domain_scores = domain_detector.get_scores(homepage_content, {"url": url})
            sorted_scores = sorted(domain_scores, key=lambda x: x.score, reverse=True)
            top_score = sorted_scores[0] if sorted_scores else None

            # Only accept domain if score is meaningful
            if top_score and top_score.score > 2.0:
                detected_domain = top_score.domain
            else:
                detected_domain = "general"

            chatbot.domain = detected_domain
            chatbot.behavior_profile = detected_domain
            await db.commit()
            logger.info(f"[INGESTION] Domain detected: {detected_domain} (score={top_score.score if top_score else 0:.1f})")

            # --- Crawl ---
            logger.info(f"[INGESTION] [STAGE: Crawling] Starting discovery for {url}")
            depth = 2
            pages, docs = await scraper.discover_assets(
                url, limit=settings.top_k * 4, depth=depth, allow_external=True
            )
            logger.info(f"[INGESTION] Discovered {len(pages)} pages, {len(docs)} docs")

            all_text = homepage_content + "\n\n"

            # --- HTML pages ---
            logger.info(f"[INGESTION] [STAGE: Extraction & Indexing HTML] Processing {len(pages)} pages")
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
                if not content or len(content.split()) < 20:
                    continue

                all_text += content + "\n\n"
                chunks = _chunk_text(content, page_url, chatbot_id, domain=detected_domain, source_type="text/html")
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
            logger.info(f"[INGESTION] [STAGE: Extraction & Indexing Docs] Processing {len(docs)} linked documents")
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
                    if not content or len(content.split()) < 20:
                        continue

                    all_text += content + "\n\n"
                    stype = "application/pdf" if doc_url.endswith(".pdf") else "application/vnd.openxmlformats"
                    chunks = _chunk_text(content, doc_url, chatbot_id, domain=detected_domain, source_type=stype)
                    if not chunks:
                        continue

                    await asyncio.to_thread(upsert_chunks, chunks)

                    doc_obj = UploadedDocument(
                        chatbot_id=chatbot_id,
                        filename=Path(doc_url).name or "document",
                        source_path=doc_url,
                        content_type=stype,
                    )
                    db.add(doc_obj)
                    await db.flush()
                    for c in chunks:
                        db.add(EmbeddingMetadata(
                            document_id=doc_obj.id,
                            chunk_id=c["chunk_id"],
                            text=c["text"],
                            metadata_json=c["metadata"],
                        ))
                finally:
                    if temp_path.exists():
                        temp_path.unlink()

            # --- Build Site Intelligence Profile ---
            logger.info(f"[INGESTION] [STAGE: Site Profile] Building contextual intelligence profile")
            from backend.utils.site_intelligence import build_site_profile
            site_profile = await build_site_profile(
                all_text=all_text,
                domain=detected_domain,
                site_url=url,
            )
            chatbot.site_profile = site_profile

            logger.info(f"[INGESTION] [STAGE: DB Commit] Finalizing database transaction")
            chatbot.status = "ready"
            chatbot.error_message = None
            await db.commit()

            logger.info(
                f"[INGESTION] Complete — chatbot={chatbot_id} domain={detected_domain} "
                f"pages={len(pages)} docs={len(docs)} "
                f"entities={len(site_profile.get('top_entities', []))}"
            )

        except Exception as e:
            logger.error(f"[INGESTION] Failed at stage for chatbot={chatbot_id}: {e}", exc_info=True)
            chatbot = await db.get(Chatbot, chatbot_id)
            if chatbot:
                chatbot.status = "error"
                chatbot.error_message = f"{type(e).__name__}: {str(e)}"
                await db.commit()
