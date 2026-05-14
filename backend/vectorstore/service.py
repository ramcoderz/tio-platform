from pathlib import Path
from threading import Lock
import faiss
import chromadb
import numpy as np
from rank_bm25 import BM25Okapi
import asyncio
import logging

logger = logging.getLogger(__name__)

from backend.rag.embeddings import embed, rerank
from backend.rag.types import RetrievedChunk
from backend.config.settings import get_settings

settings = get_settings()
Path(settings.chroma_dir).mkdir(parents=True, exist_ok=True)

# State
_faiss = faiss.IndexFlatIP(384)
_rows: list[dict] = []
_chroma = chromadb.PersistentClient(path=settings.chroma_dir).get_or_create_collection("tio_chunks")
_lock = Lock()

def _tokenize(text: str) -> list[str]:
    return text.lower().split()

def _reload_from_chroma() -> None:
    global _faiss, _rows
    try:
        count = _chroma.count()
        if count == 0: return
        
        result = _chroma.get(include=["embeddings", "documents", "metadatas"])
        ids = result.get("ids", [])
        embeddings = result.get("embeddings", [])
        documents = result.get("documents", [])
        metadatas = result.get("metadatas", [])
        
        if ids is None or embeddings is None or len(ids) == 0: return
        
        with _lock:
            _faiss = faiss.IndexFlatIP(384)
            _rows = []
            vecs = np.asarray(embeddings, dtype="float32")
            _faiss.add(vecs)
            for cid, doc, meta, vec in zip(ids, documents, metadatas, embeddings):
                _rows.append({
                    "chunk_id": cid,
                    "text": doc,
                    "document": (meta or {}).get("document", ""),
                    "metadata": meta or {},
                    "embedding": vec,
                })
    except Exception as e:
        logger.error(f"Error reloading chroma: {e}")

def initialize_vectorstore():
    _reload_from_chroma()

def upsert_chunks(chunks: list[dict]) -> None:
    if not chunks: return
    
    # Validation
    valid_chunks = []
    for c in chunks:
        if not c.get("chunk_id"):
            logger.error("[VECTORSTORE] Chunk missing ID, skipping.")
            continue
        text = c.get("text", "")
        if not isinstance(text, str) or len(text.strip()) == 0:
            logger.error(f"[VECTORSTORE] Chunk {c.get('chunk_id')} has empty text, skipping.")
            continue
        valid_chunks.append(c)

    if not valid_chunks:
        logger.error("[VECTORSTORE] No valid chunks remaining after validation.")
        return

    vectors = embed([c["text"] for c in valid_chunks])
    if len(vectors) != len(valid_chunks):
        logger.error(f"[VECTORSTORE] Embedding count ({len(vectors)}) != Chunk count ({len(valid_chunks)})")
        raise ValueError("Embedding generation mismatch")

    with _lock:
        try:
            _faiss.add(np.asarray(vectors, dtype="float32"))
            for chunk, vector in zip(valid_chunks, vectors):
                row = dict(chunk)
                row["embedding"] = vector.tolist() if hasattr(vector, "tolist") else list(vector)
                _rows.append(row)

            safe_metadatas = []
            for c in valid_chunks:
                meta = {}
                for k, val in c.get("metadata", {}).items():
                    if val is None:
                        meta[k] = ""
                    elif isinstance(val, (str, int, float, bool)):
                        meta[k] = val
                    elif isinstance(val, list):
                        meta[k] = ", ".join(str(v) for v in val)
                    else:
                        meta[k] = str(val)
                meta["document"] = str(c.get("document", ""))
                safe_metadatas.append(meta)
                
            _chroma.upsert(
                ids=[c["chunk_id"] for c in valid_chunks],
                embeddings=[v.tolist() if hasattr(v, "tolist") else list(v) for v in vectors],
                documents=[c["text"] for c in valid_chunks],
                metadatas=safe_metadatas,
            )
            logger.info(f"[VECTORSTORE] Upserted {len(valid_chunks)} chunks to FAISS & ChromaDB.")
        except Exception as e:
            logger.error(f"[VECTORSTORE] Insertion failed: {e}", exc_info=True)
            raise

def _compute_rrf(faiss_ranks: list[int], bm25_ranks: list[int], k: int = 60) -> float:
    score = 0.0
    if faiss_ranks: score += sum(1.0 / (k + r) for r in faiss_ranks)
    if bm25_ranks: score += sum(1.0 / (k + r) for r in bm25_ranks)
    return score

def _dense_search(q_vec: np.ndarray, candidates: list) -> list:
    results = []
    for row in candidates:
        score = float(np.dot(q_vec, np.asarray(row["embedding"], dtype="float32")))
        results.append((score, row))
    return sorted(results, key=lambda x: x[0], reverse=True)

def _sparse_search(q_tokens: list, candidates: list) -> list:
    if not candidates: return []
    local_corpus = [_tokenize(r["text"]) for r in candidates]
    local_bm25 = BM25Okapi(local_corpus)
    scores = local_bm25.get_scores(q_tokens)
    return [(scores[i], candidates[i]) for i in range(len(candidates))]

def retrieve(query: str, top_k: int | None = None, chatbot_id: int | None = None, domain: str | None = None) -> list[RetrievedChunk]:
    limit = top_k or settings.top_k
    q_vec = np.asarray(embed([query])[0], dtype="float32")
    q_tokens = _tokenize(query)
    
    with _lock:
        if not _rows: return []
        if not chatbot_id:
            logger.warning("[RETRIEVAL] Missing chatbot_id in retrieval request. Returning empty.")
            return []
            
        candidates = [r for r in _rows if r.get("metadata", {}).get("chatbot_id") == chatbot_id]
        if domain and domain != "general":
            candidates = [r for r in candidates if r.get("metadata", {}).get("domain") == domain]
            
        if not candidates: return []
        
        dense_res = _dense_search(q_vec, candidates)
        sparse_res = sorted(_sparse_search(q_tokens, candidates), key=lambda x: x[0], reverse=True)
        
        fused = []
        for row in candidates:
            cid = row["chunk_id"]
            d_rank = next((i for i, (_, r) in enumerate(dense_res) if r["chunk_id"] == cid), None)
            s_rank = next((i for i, (_, r) in enumerate(sparse_res) if r["chunk_id"] == cid), None)
            
            score = _compute_rrf([d_rank + 1] if d_rank is not None else [], [s_rank + 1] if s_rank is not None else [])
            if score > 0:
                fused.append((score, row))
        
        fused = sorted(fused, key=lambda x: x[0], reverse=True)[:limit]
        return [RetrievedChunk(r["chunk_id"], r["text"], float(s), r["document"], r["metadata"]) for s, r in fused]

async def async_retrieve(
    query: str, 
    top_k: int | None = None, 
    chatbot_id: int | None = None, 
    domain: str | None = None,
    workflow: str | None = None
) -> list[RetrievedChunk]:
    limit = top_k or settings.top_k
    q_vec = np.asarray(embed([query])[0], dtype="float32")
    q_tokens = _tokenize(query)
    workflow_tokens = _tokenize(workflow) if workflow else []

    
    with _lock:
        if not _rows:
            logger.warning("[RETRIEVAL] Vector store is empty — no chunks indexed yet.")
            return []
        
        if not chatbot_id:
            logger.error("[RETRIEVAL] CRITICAL: async_retrieve called WITHOUT chatbot_id. Denying global search for security.")
            return []

        candidates = [r for r in _rows if r.get("metadata", {}).get("chatbot_id") == chatbot_id]
        
        # Domain Locking: Secondary validation layer
        if domain and domain != "general":
            before_count = len(candidates)
            candidates = [r for r in candidates if r.get("metadata", {}).get("domain") == domain]
            if len(candidates) < before_count:
                logger.info(f"[RETRIEVAL] Filtered out {before_count - len(candidates)} chunks due to domain mismatch (target: {domain})")

        if not candidates:
            logger.warning(f"[RETRIEVAL] No chunks for chatbot_id={chatbot_id} domain={domain}. Has ingestion completed?")
            return []

    dense_task = asyncio.to_thread(_dense_search, q_vec, candidates)
    sparse_task = asyncio.to_thread(_sparse_search, q_tokens, candidates)
    dense_res, sparse_res_unsorted = await asyncio.gather(dense_task, sparse_task)
    sparse_res = sorted(sparse_res_unsorted, key=lambda x: x[0], reverse=True)
    
    fused = []
    q_norm = query.lower()
    for row in candidates:
        cid = row["chunk_id"]
        d_rank = next((i for i, (_, r) in enumerate(dense_res) if r["chunk_id"] == cid), None)
        s_rank = next((i for i, (_, r) in enumerate(sparse_res) if r["chunk_id"] == cid), None)
        
        score = _compute_rrf([d_rank + 1] if d_rank is not None else [], [s_rank + 1] if s_rank is not None else [])

        # Entity Boosting: If query contains entities found in this chunk
        meta = row.get("metadata", {})
        if isinstance(meta, dict):
            entities = meta.get("entities", [])
            if isinstance(entities, list):
                for ent in entities:
                    if str(ent).lower() in q_norm:
                        score += 0.15  # Stronger boost for entity match (Task: Entity Grounding)

        # Priority Boosting: Homepage/High-quality pages get a boost
        priority = meta.get("priority", 1)
        if priority > 1:
            score += (priority - 1) * 0.05

        # Workflow Boosting: Boost if chunk text contains workflow keywords
        if workflow_tokens:
            chunk_lower = row["text"].lower()
            for wt in workflow_tokens:
                if len(wt) > 3 and wt in chunk_lower:
                    score += 0.1  # Significant boost for workflow relevance


        if score > 0: fused.append((score, row))
            
    fused = sorted(fused, key=lambda x: x[0], reverse=True)[:20]

    if not fused:
        logger.warning(f"[RETRIEVAL] RRF fusion returned 0 results for query={query!r} chatbot_id={chatbot_id}")
        return []

    if len(fused) > 5 and len(query.split()) > 3:
        try:
            texts = [r["text"] for _, r in fused]
            scores = rerank(query, texts)
            reranked = sorted([(s, r) for s, (_, r) in zip(scores, fused)], key=lambda x: x[0], reverse=True)[:limit]
            return [RetrievedChunk(r["chunk_id"], r["text"], float(s), r["document"], r["metadata"]) for s, r in reranked]
        except Exception as e:
            logger.warning(f"[RETRIEVAL] Reranking failed, falling back to RRF: {e}")

    return [RetrievedChunk(r["chunk_id"], r["text"], float(s), r["document"], r["metadata"]) for s, r in fused[:limit]]

def delete_chatbot_vectors(chatbot_id: int) -> None:
    global _rows, _faiss
    with _lock:
        to_delete = [r["chunk_id"] for r in _rows if r.get("metadata", {}).get("chatbot_id") == chatbot_id]
        if not to_delete: return
        
        _rows = [r for r in _rows if r.get("metadata", {}).get("chatbot_id") != chatbot_id]
        _chroma.delete(ids=to_delete)
        _faiss = faiss.IndexFlatIP(384)
        if _rows:
            _faiss.add(np.asarray([r["embedding"] for r in _rows], dtype="float32"))

def delete_chunk_vectors(chunk_ids: list[str]) -> None:
    global _rows, _faiss
    if not chunk_ids: return
    ids = set(chunk_ids)
    with _lock:
        _rows = [r for r in _rows if r["chunk_id"] not in ids]
        _chroma.delete(ids=list(ids))
        _faiss = faiss.IndexFlatIP(384)
        if _rows:
            _faiss.add(np.asarray([r["embedding"] for r in _rows], dtype="float32"))

def purge_all() -> None:
    global _rows, _faiss
    with _lock:
        _rows = []
        _faiss = faiss.IndexFlatIP(384)
        try:
            _chroma.delete(where={})
        except: pass

def get_stats() -> dict:
    with _lock:
        return {
            "total_chunks": len(_rows),
            "vector_count": _faiss.ntotal,
            "document_count": len(set(r.get("document", "") for r in _rows if r.get("document")))
        }
