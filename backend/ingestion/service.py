import asyncio
from pathlib import Path
from uuid import uuid4
import re
import pandas as pd
import numpy as np
from docx import Document as DocxDocument
from PIL import Image, ImageOps
from pypdf import PdfReader
from fastapi import HTTPException, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from backend.config.settings import get_settings
from backend.rag.raptor import raptor_service
from backend.llm.gemini_client import gemini_client
from backend.agents.relationship_agent import extract_relationships
from backend.vectorstore.service import upsert_chunks, delete_chunk_vectors
from backend.models.entities import UploadedDocument, EmbeddingMetadata, SessionMemory
import hashlib
from sqlalchemy import select

settings = get_settings()
_ocr_reader = None


def _get_ocr():
    """Lazy-initialize EasyOCR reader on first use to avoid blocking server startup."""
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        _ocr_reader = easyocr.Reader(["en"], gpu=False)
    return _ocr_reader



def _parse(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)
    if suffix == ".docx":
        return "\n".join(p.text for p in DocxDocument(str(path)).paragraphs)
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".csv":
        df = pd.read_csv(path)
        summary = f"CSV Intelligence Report: {path.name}\nColumns: {', '.join(df.columns)}\nRows: {len(df)}\nSample Data Summary:\n{df.describe(include='all').to_string()}\nFull Content:\n{df.to_csv(index=False)}"
        return summary
    if suffix == ".xlsx":
        df = pd.read_excel(path)
        summary = f"Excel Intelligence Report: {path.name}\nSheets: {path.name}\nRows: {len(df)}\nFull Content:\n{df.to_csv(index=False)}"
        return summary
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return "\n".join(_get_ocr().readtext(str(path), detail=0))
    raise ValueError(
        "Unsupported format. Supported: .pdf, .docx, .txt, .md, .csv, .xlsx, .png, .jpg, .jpeg, .webp"
    )


def _parse_image_optimized(path: Path) -> str:
    image = Image.open(path).convert("RGB")
    width, height = image.size
    max_side = 1800
    if max(width, height) > max_side:
        ratio = max_side / float(max(width, height))
        image = image.resize((int(width * ratio), int(height * ratio)))
    gray = ImageOps.grayscale(image)
    arr = np.asarray(gray, dtype=np.uint8)
    if arr.std() < 4:
        return ""
    threshold = int(np.median(arr))
    binary = np.where(arr > threshold, 255, 0).astype(np.uint8)
    text_blocks = _get_ocr().readtext(binary, detail=0, paragraph=True)
    return "\n".join(t.strip() for t in text_blocks if t.strip())


def _chunks(text: str, document: str, session_id: str | None = None) -> list[dict]:
    text = re.sub(r"\s+", " ", text).strip()
    chunks = []
    i = 0
    while i < len(text):
        end = min(i + settings.chunk_size, len(text))
        chunks.append(
            {
                "chunk_id": str(uuid4()),
                "text": text[i:end],
                "document": document,
                "metadata": {"start": i, "end": end, "session_id": session_id},
            }
        )
        if end == len(text):
            break
        i = end - settings.chunk_overlap
    return chunks



async def ingest_file(file: UploadFile, db: AsyncSession, session_id: str | None = None) -> dict:
    timings: dict[str, float] = {}
    started = asyncio.get_running_loop().time()
    
    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()
    
    # Check for duplicate
    existing = await db.execute(select(UploadedDocument).where(UploadedDocument.file_hash == file_hash))
    existing_doc = existing.scalar_one_or_none()
    if existing_doc:
        return {
            "document_id": existing_doc.id, 
            "status": "already_exists", 
            "filename": existing_doc.filename,
            "message": "Document already indexed."
        }

    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    path = Path(settings.upload_dir) / f"{uuid4()}_{file.filename}"
    path.write_bytes(content)
    try:
        parse_started = asyncio.get_running_loop().time()
        suffix = path.suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
            text = await asyncio.to_thread(_parse_image_optimized, path)
        else:
            text = await asyncio.to_thread(_parse, path)
        timings["parse_ms"] = round((asyncio.get_running_loop().time() - parse_started) * 1000, 2)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    chunk_started = asyncio.get_running_loop().time()
    chunks = await asyncio.to_thread(_chunks, text, file.filename, session_id)
    chunks = [chunk for chunk in chunks if chunk["text"].strip()]
    seen = set()
    deduped = []
    for chunk in chunks:
        key = chunk["text"][:180]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(chunk)
    chunks = deduped
    timings["chunk_ms"] = round((asyncio.get_running_loop().time() - chunk_started) * 1000, 2)
    if not chunks:
        raise HTTPException(status_code=400, detail="No readable text found in the uploaded file.")

    chunk_ids = [chunk["chunk_id"] for chunk in chunks]
    try:
        embed_started = asyncio.get_running_loop().time()
        await asyncio.to_thread(upsert_chunks, chunks)
        
        # RAPTOR: Build hierarchical summaries
        raptor_summaries = await raptor_service.build_hierarchy(chunks)
        if raptor_summaries:
            await asyncio.to_thread(upsert_chunks, raptor_summaries)
            chunks.extend(raptor_summaries) # Add summaries to the list to be persisted in DB
            # Update chunk_ids to include summaries for proper rollback
            chunk_ids.extend([c["chunk_id"] for c in raptor_summaries])
            
        timings["index_ms"] = round((asyncio.get_running_loop().time() - embed_started) * 1000, 2)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Embedding service unavailable during ingestion. "
                "Ensure model download is complete and retry."
            ),
        ) from exc
    doc = UploadedDocument(
        filename=file.filename, 
        source_path=str(path), 
        content_type=file.content_type or "",
        file_hash=file_hash,
        summary=None, # To be updated after AI pass
        intel_report=None
    )
    db.add(doc)
    await db.flush()
    if session_id:
        db.add(SessionMemory(session_id=session_id, key="uploaded_document_id", value=str(doc.id)))
    for c in chunks:
        db.add(
            EmbeddingMetadata(
                document_id=doc.id,
                chunk_id=c["chunk_id"],
                text=c["text"],
                metadata_json=c["metadata"],
            )
        )
    try:
        await db.commit()
    except SQLAlchemyError as exc:
        await db.rollback()
        await asyncio.to_thread(delete_chunk_vectors, chunk_ids)
        raise HTTPException(status_code=500, detail="Failed to persist ingestion metadata.") from exc

    # 4. Trigger AI Intelligence Pass in background (Non-blocking)
    asyncio.create_task(run_intelligence_pass(doc.id, text, path, suffix, session_id))

    timings["total_ms"] = round((asyncio.get_running_loop().time() - started) * 1000, 2)
    return {"document_id": doc.id, "chunks": len(chunks), "timings": timings}


async def run_intelligence_pass(doc_id: int, text: str, path: Path, suffix: str, session_id: str | None):
    """Heavy AI processing moved to background to prevent request timeout."""
    from backend.db.session import SessionLocal
    async with SessionLocal() as db:
        try:
            from backend.llm.ollama_client import ollama_client
            from backend.models.entities import UploadedDocument, SessionMemory
            
            doc = await db.get(UploadedDocument, doc_id)
            if not doc: return

            # RAPTOR: Build hierarchical summaries
            from backend.rag.raptor import raptor_service
            from backend.vectorstore.service import upsert_chunks, get_chunks_by_doc
            from backend.models.entities import EmbeddingMetadata
            
            # Fetch the chunks we just created
            chunks_stmt = select(EmbeddingMetadata).where(EmbeddingMetadata.document_id == doc_id)
            db_chunks = (await db.execute(chunks_stmt)).scalars().all()
            
            if db_chunks:
                # Format for raptor_service
                chunk_list = [{"chunk_id": c.chunk_id, "text": c.text, "metadata": c.metadata_json} for c in db_chunks]
                raptor_summaries = await raptor_service.build_hierarchy(chunk_list)
                if raptor_summaries:
                    # Index the summaries
                    await asyncio.to_thread(upsert_chunks, raptor_summaries)
                    # Persist metadata
                    for c in raptor_summaries:
                        db.add(EmbeddingMetadata(
                            document_id=doc_id,
                            chunk_id=c["chunk_id"],
                            text=c["text"],
                            metadata_json=c["metadata"]
                        ))
            
            if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
                vision_prompt = "Extract all text, data from tables, and describe any charts or diagrams in this image in detail."
                vision_analysis = await gemini_client.analyze_image(str(path), vision_prompt)
                if vision_analysis:
                    doc.intel_report = vision_analysis
            
            summary_prompt = f"Summarize this document content in 2 sentences. \nContent: {text[:2000]}"
            summary = await ollama_client.generate(summary_prompt, model=settings.ollama_model)
            doc.summary = summary
            
            if session_id:
                db.add(SessionMemory(session_id=session_id, key=f"doc_summary_{doc.id}", value=summary))

            # GraphRAG-lite Relationship Mapping
            await extract_relationships(doc.id, text, db)
            
            await db.commit()
        except Exception as e:
            print(f"Background intelligence pass failed for doc {doc_id}: {e}")
