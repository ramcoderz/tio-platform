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
_bm25: BM25Okapi | None = None
_chroma = chromadb.PersistentClient(path=settings.chroma_dir).get_or_create_collection("tio_chunks")
_lock = Lock()

def _tokenize(text: str) -> list[str]:
    return text.lower().split()

def _rebuild_bm25():
    global _bm25
    if not _rows:
        _bm25 = None
        return
    tokenized_corpus = [_tokenize(r["text"]) for r in _rows]
    _bm25 = BM25Okapi(tokenized_corpus)

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
            _rebuild_bm25()
    except Exception as e:
        logger.error(f"Error reloading chroma: {e}")

def initialize_vectorstore():
    _reload_from_chroma()

def upsert_chunks(chunks: list[dict]) -> None:
    if not chunks: return
    vectors = embed([c["text"] for c in chunks])
    with _lock:
        _faiss.add(np.asarray(vectors, dtype="float32"))
        for chunk, vector in zip(chunks, vectors):
            row = dict(chunk)
            row["embedding"] = vector.tolist() if hasattr(vector, "tolist") else list(vector)
            _rows.append(row)
            
        _rebuild_bm25()

        safe_metadatas = []
        for c in chunks:
            meta = {
                k: (str(val) if val is not None and not isinstance(val, (str, int, float, bool)) else ("" if val is None else val))
                for k, val in c.get("metadata", {}).items()
            }
            meta["document"] = c.get("document", "")
            safe_metadatas.append(meta)
            
        _chroma.add(
            ids=[c["chunk_id"] for c in chunks],
            embeddings=[v.tolist() if hasattr(v, "tolist") else list(v) for v in vectors],
            documents=[c["text"] for c in chunks],
            metadatas=safe_metadatas,
        )

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

async def async_retrieve(query: str, top_k: int | None = None, chatbot_id: int | None = None, domain: str | None = None) -> list[RetrievedChunk]:
    limit = top_k or settings.top_k
    q_vec = np.asarray(embed([query])[0], dtype="float32")
    q_tokens = _tokenize(query)
    
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
                        score += 0.02  # Boost for entity match
        
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
        _rebuild_bm25()

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
        _rebuild_bm25()

def purge_all() -> None:
    global _rows, _faiss, _bm25
    with _lock:
        _rows = []
        _faiss = faiss.IndexFlatIP(384)
        _bm25 = None
        try:
            _chroma.delete(where={})
        except: pass

def get_stats() -> dict:
    with _lock:
        return {
            "total_chunks": len(_rows),
            "vector_count": _faiss.ntotal,
            "document_count": len(set(r.get("document", "") for r in _rows if r.get("document"))),
            "bm25_active": _bm25 is not None
        }
