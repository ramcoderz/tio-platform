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
import time
import mimetypes
from pathlib import Path
from uuid import uuid4
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)
from backend.utils.console import console

@dataclass
class IngestionProfiler:
    chatbot_id: int
    start_time: float = field(default_factory=time.monotonic)
    stages: dict[str, float] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=lambda: {
        "pages_crawled": 0,
        "chunks_generated": 0,
        "embeddings_completed": 0,
        "vectors_inserted": 0,
        "failed_chunks": 0,
        "skipped_pages": 0,
        "total_pages": 0
    })
    _last_update: float = field(default_factory=time.monotonic)
    _last_progress: int = 0
    
    def start_stage(self, stage: str):
        self.stages[stage] = time.monotonic()
        console.stage(stage, "Started...")

    def end_stage(self, stage: str):
        if stage in self.stages and isinstance(self.stages[stage], float):
            duration = time.monotonic() - self.stages[stage]
            self.stages[stage] = round(duration, 2)
            console.success(f"Complete ({duration:.1f}s)", stage=stage)
    
    def update_counts(self, **kwargs):
        for k, v in kwargs.items():
            if k in self.counts:
                self.counts[k] = v
        self._last_update = time.monotonic()

    def get_eta(self, progress: int) -> str:
        """Calculate ETA based on overall progress."""
        if progress <= 5: return "calculating..."
        if progress >= 100: return "0s"
        
        elapsed = time.monotonic() - self.start_time
        total_est = (elapsed / progress) * 100
        remaining = max(0, total_est - elapsed)
        
        if remaining < 60:
            return f"~{int(remaining)}s remaining"
        return f"~{int(remaining // 60)}m {int(remaining % 60)}s remaining"

    def get_rate(self, count_key: str) -> float:
        """Items per second since start."""
        elapsed = time.monotonic() - self.start_time
        count = self.counts.get(count_key, 0)
        return round(count / max(elapsed, 1), 1)

    def detect_stall(self, progress: int, stage: str, last_item: str = "", threshold: int = 40) -> bool:
        now = time.monotonic()
        if progress > self._last_progress:
            self._last_progress = progress
            self._last_update = now
            return False
        
        idle_time = int(now - self._last_update)
        if idle_time > threshold:
            console.warning(
                f"Possible ingestion stall detected (Idle {idle_time}s)\n"
                f"       Stage: {stage.upper()}\n"
                f"       Last processed: {last_item or 'N/A'}"
            )
            return True
        return False

    def log_terminal_progress(self, progress: int, stage: str):
        eta = self.get_eta(progress)
        
        if stage.upper() == "INDEXING":
            extra = f"{self.counts['embeddings_completed']}/{self.counts['chunks_generated']} chunks processed | ETA: {eta}"
        elif stage.upper() == "CRAWLING":
            extra = f"{self.counts['pages_crawled']}/{self.counts['total_pages'] if self.counts['total_pages'] else '?'} pages discovered | ETA: {eta}"
        else:
            extra = f"Pages: {self.counts['pages_crawled']} | Chunks: {self.counts['chunks_generated']} | ETA: {eta}"
            
        console.progress(stage, progress, 100, extra=extra)
        if progress == 100:
            console.clear_line()
            console.success("Chatbot READY", stage="READY")

    def log_summary(self):
        total = round(time.monotonic() - self.start_time, 2)
        summary = {
            "chatbot_id": self.chatbot_id,
            "total_time": total,
            "stages": self.stages,
            "counts": self.counts,
            "avg_rate": self.get_rate("embeddings_completed")
        }
        
        console.separator()
        console.success(f"Ingestion Completed in {int(total // 60)}m {int(total % 60)}s", stage="FINALIZING")
        print(f"       Pages: {self.counts['pages_crawled']} | Chunks: {self.counts['chunks_generated']}")
        print(f"       Skipped: {self.counts['skipped_pages']} | Failed Chunks: {self.counts['failed_chunks']}")
        console.separator()
        
        return summary

    @property
    def elapsed(self):
        return round(time.monotonic() - self.start_time, 1)

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
from backend.utils.entities import extract_entities as robust_extract_entities, extract_entities_batch
from backend.utils.site_intelligence import build_site_profile

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


class MimeInference:
    """Centralized MIME type detection for TiO ingestion."""
    
    TYPE_MAP = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".html": "text/html",
        ".htm": "text/html",
    }

    @classmethod
    def infer(cls, path_or_url: str, content_type_header: str = None) -> str:
        if content_type_header:
            # Clean header (e.g. "text/html; charset=UTF-8" -> "text/html")
            clean_type = content_type_header.split(";")[0].strip().lower()
            if clean_type and clean_type != "application/octet-stream":
                return clean_type

        # Use extension-based detection
        ext = Path(path_or_url).suffix.lower()
        if ext in cls.TYPE_MAP:
            return cls.TYPE_MAP[ext]

        # Use standard mimetypes library
        guess, _ = mimetypes.guess_type(path_or_url)
        if guess:
            return guess

        # Default fallback
        return "application/octet-stream"


# ---------------------------------------------------------------------------
# File Parsing
# ---------------------------------------------------------------------------

_UNICODE_MAP = {
    "\u2192": "->", "\u2190": "<-", "\u2013": "-", "\u2014": "--",
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2022": "*", "\u00a0": " ", "\u2026": "...",
}

def _sanitize_unicode(text: str) -> str:
    """Replace problematic Unicode characters with ASCII equivalents."""
    for char, replacement in _UNICODE_MAP.items():
        text = text.replace(char, replacement)
    return text.encode("utf-8", errors="replace").decode("utf-8")


def _parse_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        raw = "\n".join(
            (p.extract_text() or "") for p in PdfReader(str(path)).pages
        )
        return _sanitize_unicode(raw)
    if suffix == ".docx":
        raw = "\n".join(p.text for p in DocxDocument(str(path)).paragraphs)
        return _sanitize_unicode(raw)
    if suffix in {".txt", ".md"}:
        return _sanitize_unicode(path.read_text(encoding="utf-8", errors="ignore"))
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


def _extract_entities(text: str, quality_score: float) -> list[str]:
    """Link to centralized entity extraction — optimized to skip low-quality text."""
    if quality_score < 0.35 or len(text) < 150:
        return []
    return robust_extract_entities(text)


# Section headers that indicate profile/CV/resume content
_PROFILE_SECTION_KEYWORDS = {
    "experience", "work history", "employment", "career",
    "qualification", "qualifications", "education", "academic background",
    "publications", "research", "projects", "achievements",
    "skills", "expertise", "appointments", "positions held",
}

# Source patterns that indicate profile/CV documents
_PROFILE_SOURCE_PATTERNS = re.compile(
    r"(faculty|staff|professor|dr\.|phd|cv|resume|profile|bio|biography|about-us|team)",
    re.IGNORECASE
)


def _detect_section_title(buf: str) -> str:
    """Detect if the first line of a chunk is a section header."""
    first_line = buf.strip().split("\n")[0].strip()
    if len(first_line) < 60 and first_line:
        lower = first_line.lower()
        for kw in _PROFILE_SECTION_KEYWORDS:
            if kw in lower:
                return first_line
    return ""


def _is_profile_doc(source: str, source_type: str) -> bool:
    """Check if the source is likely a faculty/profile/CV document."""
    is_pdf = source_type in ("application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    has_profile_pattern = bool(_PROFILE_SOURCE_PATTERNS.search(source))
    return is_pdf or has_profile_pattern


def _chunk_text(
    text: str,
    source: str,
    chatbot_id: int,
    domain: str = "general",
    source_type: str = "text/html",
) -> list[dict]:
    """Section-aware chunking with quality filtering, entity extraction, and profile metadata."""
    # Sanitize unicode before chunking
    text = _sanitize_unicode(text)
    sections = _split_into_sections(text)
    chunks: list[dict] = []
    seen_hashes: set[str] = set()
    buffer = ""
    is_profile = _is_profile_doc(source, source_type)

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

        h = hashlib.md5(buf.encode()).hexdigest()
        if h in seen_hashes:
            return
        seen_hashes.add(h)

        q_score = _content_score(buf)
        section_title = _detect_section_title(buf)

        # Priority scoring:
        # 5 = profile/CV section (experience, publications, etc.)
        # 4 = profile doc without matching section
        # 3 = homepage / shallow URL
        # 2 = high-quality general content
        # 1 = general content
        if is_profile and section_title:
            priority = 5
        elif is_profile:
            priority = 4
        elif source == "/" or source.endswith(("index.html", "index.php")) or len(source.split("/")) < 4:
            priority = 3
        elif q_score > 0.6:
            priority = 2
        else:
            priority = 1

        # Extract document title from source path
        doc_title = Path(source.split("?")[0]).stem.replace("-", " ").replace("_", " ").title() if "/" in source else source

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
                "entities": [],  # Filled in batch after chunking
                "quality_score": q_score,
                "priority": priority,
                "is_profile_doc": is_profile,
                "section_title": section_title,
                "document_title": doc_title,
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

    console.info(f"{source!r} -> {len(chunks)} quality chunks from {len(sections)} sections", stage="CHUNKING")
    return chunks


# ---------------------------------------------------------------------------
# File Upload Ingestion
# ---------------------------------------------------------------------------

async def ingest_file(chatbot_id: int, file: UploadFile, db: AsyncSession) -> dict:
    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()

    try:
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

        text = await asyncio.to_thread(_parse_file, path)
        chatbot = await db.get(Chatbot, chatbot_id)
        domain = chatbot.domain if chatbot else "general"
        
        inferred_type = MimeInference.infer(file.filename, file.content_type)
        chunks = _chunk_text(text, file.filename, chatbot_id, domain=domain, source_type=inferred_type)
        
        if not chunks:
            raise ValueError("No readable text found in file (or all content filtered as boilerplate).")

        await asyncio.to_thread(upsert_chunks, chunks)

        doc = UploadedDocument(
            chatbot_id=chatbot_id,
            filename=file.filename,
            source_path=str(path),
            content_type=inferred_type or "application/octet-stream",
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
        console.error(f"[INGEST][DB] Transaction failed for {file.filename}: {e}")
        await db.rollback()
        if 'path' in locals() and path.exists():
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
# Website Ingestion (background job logic)
# ---------------------------------------------------------------------------

async def ingest_website(chatbot_id: int, url: str) -> int:
    """Backward compatibility wrapper: submits to the job worker."""
    from backend.ingestion.worker import ingestion_worker
    return await ingestion_worker.submit_job(chatbot_id)


async def ingest_website_core(chatbot_id: int, job_id: int) -> None:
    """
    The controlled core ingestion logic. 
    Updates both Chatbot.status_json AND IngestionJob record.
    """
    from backend.db.session import SessionLocal
    from backend.utils.domain_intelligence import domain_detector
    from backend.utils.site_intelligence import build_site_profile
    from backend.models.entities import IngestionJob, UploadedDocument, EmbeddingMetadata
    from backend.utils.events import broadcast_ingestion_event

    profiler = IngestionProfiler(chatbot_id)
    
    async with SessionLocal() as db:
        async def update_stage(stage_name: str, progress: int, message: str, counts: dict = None):
            try:
                from backend.db.session import SessionLocal
                async with SessionLocal() as status_db:
                    curr_job = await status_db.get(IngestionJob, job_id)
                    curr_cb = await status_db.get(Chatbot, chatbot_id)
                    if not curr_job or not curr_cb: return
                    
                    if counts: profiler.update_counts(**counts)
                    profiler.detect_stall(progress, stage_name, message)
                    profiler.log_terminal_progress(progress, stage_name)

                    curr_job.current_stage = stage_name
                    curr_job.progress = progress
                    if counts:
                        if "total_chunks" in counts: curr_job.total_chunks = counts["total_chunks"]
                        if "indexed_chunks" in counts: curr_job.indexed_chunks = counts["indexed_chunks"]
                        if "failed_chunks" in counts: curr_job.failed_chunks = counts["failed_chunks"]

                    status_data = {
                        "stage": stage_name,
                        "progress": progress,
                        "message": message,
                        "eta": profiler.get_eta(progress),
                        "elapsed": profiler.elapsed,
                        "job_id": job_id,
                        **(profiler.counts)
                    }
                    curr_cb.status_json = status_data
                    await status_db.commit()
                    
                await broadcast_ingestion_event(chatbot_id, "progress", status_data)
            except Exception as se:
                logger.error(f"[STAGE_ERROR] Failed to update stage {stage_name}: {se}")

        try:
            chatbot = await db.get(Chatbot, chatbot_id)
            job = await db.get(IngestionJob, job_id)
            if not chatbot or not job: return

            url = chatbot.website_url

            # 1. Domain Detection & Crawl Discovery
            await update_stage("crawling", 5, "Discovering pages...")

            profiler.start_stage("crawling")
            try:
                homepage_content = await scraper.extract_content(url)
            except Exception as e:
                console.critical(f"Crawler stall/failed at homepage: {e}", stage="CRAWLING")
                raise e
            
            # Fast domain detection (Local/Deterministic)
            domain_scores = domain_detector.get_scores(homepage_content, {"url": url})
            sorted_scores = sorted(domain_scores, key=lambda x: x.score, reverse=True)
            detected_domain = sorted_scores[0].domain if sorted_scores and sorted_scores[0].score > 2.0 else "general"
            chatbot.domain = detected_domain
            chatbot.behavior_profile = detected_domain
            await db.commit()

            try:
                # STABILIZATION: Set allow_external=False to ensure focused ingestion
                pages, docs = await asyncio.wait_for(
                    scraper.discover_assets(url, limit=20, depth=1, allow_external=False),
                    timeout=120.0
                )
                profiler.update_counts(total_pages=len(pages))
            except asyncio.TimeoutError:
                logger.error(f"[INGEST] TIMEOUT during crawling for chatbot {chatbot_id}. Falling back to homepage.")
                pages, docs = [url], []
            
            profiler.end_stage("crawling")
            
            # 2. Page Extraction
            await update_stage("extracting", 20, f"Extracting {len(pages)} pages...", {"pages_crawled": 0})
            profiler.start_stage("extraction")
            
            semaphore = asyncio.Semaphore(5)
            async def process_page(page_url: str):
                async with semaphore:
                    try:
                        content = await scraper.extract_content(page_url)
                        return (content, page_url) if content and len(content.split()) > 20 else None
                    except Exception as e:
                        logger.warning(f"Extraction failed for {page_url}: {e}")
                        return None

            results = await asyncio.wait_for(
                asyncio.gather(*(process_page(p) for p in pages), return_exceptions=True),
                timeout=240.0
            )
            extracted = [r for r in results if isinstance(r, tuple)]
            profiler.update_counts(pages_crawled=len(extracted))
            profiler.end_stage("extraction")

            # 3. Chunking & Processing
            await update_stage("chunking", 40, "Processing and chunking content...")
            profiler.start_stage("chunking")
            all_chunks = []
            all_text_buffer = [homepage_content]
            
            for content, p_url in extracted:
                all_text_buffer.append(content)
                all_chunks.extend(_chunk_text(content, p_url, chatbot_id, domain=detected_domain))

            # Handle docs
            doc_types = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".txt": "text/plain", ".md": "text/markdown"}
            for doc_url in docs:
                try:
                    temp_path = await asyncio.wait_for(download_document(doc_url), timeout=30.0)
                    if temp_path:
                        content = await asyncio.to_thread(_parse_file, str(temp_path))
                        if content and len(content.split()) >= 20:
                            ext = temp_path.suffix.lower()
                            s_type = doc_types.get(ext, "application/octet-stream")
                            all_text_buffer.append(content)
                            all_chunks.extend(_chunk_text(content, doc_url, chatbot_id, domain=detected_domain, source_type=s_type))
                        if temp_path.exists(): temp_path.unlink()
                except Exception as e:
                    logger.warning(f"Failed to process doc {doc_url}: {e}")

            if len(all_chunks) > 1200:
                all_chunks = all_chunks[:1200]
            
            total_chunks = len(all_chunks)
            profiler.update_counts(chunks_generated=total_chunks)
            profiler.end_stage("chunking")

            # 4. Embedding & Indexing (Batched)
            indexed_count = 0
            failed_count = 0
            if all_chunks:
                profiler.start_stage("indexing")
                logger.info(f"[STABILIZATION] START indexing for {total_chunks} chunks - No external APIs allowed")
                batch_size = 100
                total_batches = (total_chunks + batch_size - 1) // batch_size

                for i in range(0, total_chunks, batch_size):
                    batch = all_chunks[i:i+batch_size]
                    batch_num = (i // batch_size) + 1
                    
                    await update_stage("indexing", 50 + int((batch_num/total_batches)*30), 
                                     f"Indexing batch {batch_num}/{total_batches}...",
                                     {"total_chunks": total_chunks, "embeddings_completed": indexed_count, "failed_chunks": failed_count})
                    
                    try:
                        # Vector insertion
                        await asyncio.wait_for(asyncio.to_thread(upsert_chunks, batch), timeout=90.0)
                        
                        # Metadata persistence with transactional isolation
                        doc_cache = {}
                        path_to_type = {}
                        for c in batch:
                            if c["document"] not in path_to_type:
                                path_to_type[c["document"]] = c["metadata"].get("source_type", "text/html")

                        for path, c_type in path_to_type.items():
                            # Ensure content_type is NEVER None
                            final_type = c_type or "text/html"
                            
                            doc = (await db.execute(select(UploadedDocument).where(
                                UploadedDocument.chatbot_id == chatbot_id,
                                UploadedDocument.source_path == path
                            ))).scalar_one_or_none()
                            
                            if not doc:
                                try:
                                    doc = UploadedDocument(
                                        chatbot_id=chatbot_id, 
                                        filename=path.split("/")[-1] or "page", 
                                        source_path=path,
                                        content_type=final_type
                                    )
                                    db.add(doc)
                                    await db.flush()
                                except Exception as dbe:
                                    console.error(f"[ERROR][DB] Missing content_type or integrity failure for {path}: {dbe}")
                                    await db.rollback()
                                    continue # Skip this document but keep ingestion alive
                                    
                            doc_cache[path] = doc.id
                        
                        # Insert metadata batch
                        from sqlalchemy import insert
                        meta_batch = []
                        for c in batch:
                            if c["document"] in doc_cache:
                                meta_batch.append({
                                    "document_id": doc_cache[c["document"]], 
                                    "chunk_id": c["chunk_id"], 
                                    "text": c["text"], 
                                    "metadata": c["metadata"]
                                })

                        if meta_batch:
                            await db.execute(insert(EmbeddingMetadata), meta_batch)
                            await db.commit()
                            indexed_count += len(batch)
                        else:
                            console.warning(f"[WARNING] Skipped malformed batch {batch_num}")
                            failed_count += len(batch)
                            
                    except Exception as e:
                        console.error(f"[ROLLBACK] Batch {batch_num} failed, rolling back safely: {e}")
                        await db.rollback()
                        failed_count += len(batch)
                
                profiler.end_stage("indexing")

            # 5. Entity Enrichment & Site Profile
            await update_stage("finalizing", 90, "Finalizing intelligence profile...")
            
            # Site Profile (LLM-based but Local/Self-contained)
            try:
                logger.info(f"[STABILIZATION] Finalizing local intelligence profile for {url}")
                full_text = "\n\n".join(all_text_buffer[:30])
                site_profile = await asyncio.wait_for(
                    build_site_profile(all_text=full_text, domain=detected_domain, site_url=url),
                    timeout=60.0
                )
                chatbot.site_profile = site_profile
                await db.commit()
            except Exception as e:
                logger.warning(f"[STABILIZATION] Profile generation skipped or timed out: {e}")

            # 6. Complete
            await update_stage("ready", 100, "Ready", 
                             {"total_chunks": total_chunks, "embeddings_completed": indexed_count, "failed_chunks": failed_count})
            
            profiler.log_summary()
            logger.info(f"END ingestion for chatbot {chatbot_id}. Success={indexed_count}, Fail={failed_count}")

        except Exception as e:
            logger.error(f"[INGESTION] FAILED for chatbot={chatbot_id}: {e}", exc_info=True)
            # Worker will handle final error state update
            raise e
