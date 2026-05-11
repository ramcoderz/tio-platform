from pathlib import Path
from threading import Lock
import faiss
import chromadb
import numpy as np
from rank_bm25 import BM25Okapi
from backend.rag.embeddings import embed, rerank
from backend.rag.types import RetrievedChunk
from backend.config.settings import get_settings

settings = get_settings()
Path(settings.chroma_dir).mkdir(parents=True, exist_ok=True)
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
    """Repopulate in-memory FAISS + _rows + BM25 from persisted ChromaDB on startup."""
    global _faiss, _rows
    try:
        count = _chroma.count()
        if count == 0:
            return
        result = _chroma.get(include=["embeddings", "documents", "metadatas"])
        ids = result.get("ids", [])
        embeddings = result.get("embeddings", [])
        documents = result.get("documents", [])
        metadatas = result.get("metadatas", [])
        if ids is None or embeddings is None or len(ids) == 0:
            return
        with _lock:
            _faiss = faiss.IndexFlatIP(384)
            _rows = []
            vecs = np.asarray(embeddings, dtype="float32")
            _faiss.add(vecs)
            for chunk_id, doc_text, meta, vec in zip(ids, documents, metadatas, embeddings):
                _rows.append({
                    "chunk_id": chunk_id,
                    "text": doc_text,
                    "document": (meta or {}).get("document", ""),
                    "metadata": meta or {},
                    "embedding": vec,
                })
            _rebuild_bm25()
    except Exception:
        pass


_reload_from_chroma()


def upsert_chunks(chunks: list[dict]) -> None:
    if not chunks:
        return
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
    if faiss_ranks:
        score += sum(1.0 / (k + rank) for rank in faiss_ranks)
    if bm25_ranks:
        score += sum(1.0 / (k + rank) for rank in bm25_ranks)
    return score


def retrieve(query: str, top_k: int | None = None, session_id: str | None = None) -> list[RetrievedChunk]:
    limit = top_k or settings.top_k
    q_vec = np.asarray(embed([query])[0], dtype="float32")
    q_tokens = _tokenize(query)
    
    with _lock:
        if not _rows:
            return []
            
        candidates = _rows
        if session_id:
            session_candidates = [row for row in _rows if row.get("metadata", {}).get("session_id") == session_id]
            if session_candidates:
                candidates = session_candidates
                
def _dense_search(q_vec: np.ndarray, candidates: list) -> list:
    faiss_scores = []
    for row in candidates:
        score = float(np.dot(q_vec, np.asarray(row["embedding"], dtype="float32")))
        faiss_scores.append((score, row))
    return sorted(faiss_scores, key=lambda x: x[0], reverse=True)

def _sparse_search(q_tokens: list, candidates: list) -> list:
    if not candidates: return []
    if _bm25 and candidates == _rows:
        scores = _bm25.get_scores(q_tokens)
        return [(scores[i], _rows[i]) for i in range(len(_rows))]
    else:
        local_corpus = [_tokenize(r["text"]) for r in candidates]
        local_bm25 = BM25Okapi(local_corpus)
        scores = local_bm25.get_scores(q_tokens)
        return [(scores[i], candidates[i]) for i in range(len(candidates))]

def retrieve(query: str, top_k: int | None = None, session_id: str | None = None) -> list[RetrievedChunk]:
    limit = top_k or settings.top_k
    q_vec = np.asarray(embed([query])[0], dtype="float32")
    q_tokens = _tokenize(query)
    
    with _lock:
        if not _rows:
            return []
            
        candidates = _rows
        if session_id:
            session_candidates = [row for row in _rows if row.get("metadata", {}).get("session_id") == session_id]
            if session_candidates:
                candidates = session_candidates
                
        # 1. FAISS Retrieval (Dense)
        faiss_ranked = _dense_search(q_vec, candidates)
        
        # 2. BM25 Retrieval (Sparse)
        bm25_ranked = sorted(_sparse_search(q_tokens, candidates), key=lambda x: x[0], reverse=True)
        
        # 3. RRF Fusion
        fused_results = []
        for row in candidates:
            chunk_id = row["chunk_id"]
            faiss_rank = next((i for i, (_, r) in enumerate(faiss_ranked) if r["chunk_id"] == chunk_id), None)
            bm25_rank = next((i for i, (_, r) in enumerate(bm25_ranked) if r["chunk_id"] == chunk_id), None)
            
            f_ranks = [faiss_rank + 1] if faiss_rank is not None else []
            b_ranks = [bm25_rank + 1] if bm25_rank is not None else []
            
            rrf_score = _compute_rrf(f_ranks, b_ranks)
            if rrf_score > 0:
                fused_results.append((rrf_score, row))
                
        # Get top 20 candidates for cross-encoder reranking
        fused_ranked = sorted(fused_results, key=lambda x: x[0], reverse=True)[:20]

async def async_retrieve(query: str, top_k: int | None = None, session_id: str | None = None) -> list[RetrievedChunk]:
    import asyncio
    limit = top_k or settings.top_k
    q_vec = np.asarray(embed([query])[0], dtype="float32")
    q_tokens = _tokenize(query)
    
    # Get candidates under lock
    with _lock:
        if not _rows: return []
        candidates = _rows
        if session_id:
            session_candidates = [row for row in _rows if row.get("metadata", {}).get("session_id") == session_id]
            if session_candidates: candidates = session_candidates
    
    # Parallel Dense and Sparse Search
    # Note: These are wrapped in to_thread because they are CPU bound
    faiss_ranked_task = asyncio.to_thread(_dense_search, q_vec, candidates)
    bm25_ranked_task = asyncio.to_thread(_sparse_search, q_tokens, candidates)
    
    faiss_ranked, bm25_scores = await asyncio.gather(faiss_ranked_task, bm25_ranked_task)
    bm25_ranked = sorted(bm25_scores, key=lambda x: x[0], reverse=True)

    # 3. RRF Fusion
    fused_results = []
    for row in candidates:
        chunk_id = row["chunk_id"]
        faiss_rank = next((i for i, (_, r) in enumerate(faiss_ranked) if r["chunk_id"] == chunk_id), None)
        bm25_rank = next((i for i, (_, r) in enumerate(bm25_ranked) if r["chunk_id"] == chunk_id), None)
        
        f_ranks = [faiss_rank + 1] if faiss_rank is not None else []
        b_ranks = [bm25_rank + 1] if bm25_rank is not None else []
        
        rrf_score = _compute_rrf(f_ranks, b_ranks)
        if rrf_score > 0:
            fused_results.append((rrf_score, row))
            
    fused_ranked = sorted(fused_results, key=lambda x: x[0], reverse=True)[:20]

    if not fused_ranked: return []

    # 4. Conditional Reranking (Optimization)
    # Only rerank if there's enough complexity or many candidates
    if len(fused_ranked) > 5 and len(query.split()) > 5:
        texts_to_rerank = [row["text"] for _, row in fused_ranked]
        try:
            rerank_scores = rerank(query, texts_to_rerank)
            reranked_results = sorted([
                (score, row) for score, (_, row) in zip(rerank_scores, fused_ranked) if score > -10.0
            ], key=lambda x: x[0], reverse=True)[:limit]
            
            return [
                RetrievedChunk(row["chunk_id"], row["text"], float(score), row["document"], row["metadata"])
                for score, row in reranked_results
            ]
        except Exception: pass
    
    # Fallback to RRF
    return [
        RetrievedChunk(row["chunk_id"], row["text"], float(score), row["document"], row["metadata"])
        for score, row in fused_ranked[:limit]
    ]


def vector_count() -> int:
    with _lock:
        return _chroma.count()


def delete_session_vectors(session_id: str) -> list[str]:
    global _rows, _faiss
    with _lock:
        target_rows = [row for row in _rows if row.get("metadata", {}).get("session_id") == session_id]
        if not target_rows:
            return []

        chunk_ids = [row["chunk_id"] for row in target_rows]
        _rows = [row for row in _rows if row.get("metadata", {}).get("session_id") != session_id]
        _chroma.delete(ids=chunk_ids)
        _faiss = faiss.IndexFlatIP(384)
        if _rows:
            embeddings = np.asarray([row["embedding"] for row in _rows], dtype="float32")
            _faiss.add(embeddings)
        return chunk_ids


def delete_chunk_vectors(chunk_ids: list[str]) -> None:
    global _rows, _faiss
    if not chunk_ids:
        return
    ids = set(chunk_ids)
    with _lock:
        _rows = [row for row in _rows if row["chunk_id"] not in ids]
        _chroma.delete(ids=list(ids))
        _faiss = faiss.IndexFlatIP(384)
        if _rows:
            embeddings = np.asarray([row["embedding"] for row in _rows], dtype="float32")
            _faiss.add(embeddings)

def purge_all() -> None:
    global _rows, _faiss, _bm25
    with _lock:
        _rows = []
        _faiss = faiss.IndexFlatIP(384)
        _bm25 = None
        # Use Chroma's reset or just delete the collection
        try:
            _chroma.delete(where={}) # Delete all
        except:
            pass

def get_stats() -> dict:
    with _lock:
        return {
            "total_chunks": len(_rows),
            "vector_count": _faiss.ntotal,
            "document_count": len(set(r.get("document", "") for r in _rows if r.get("document"))),
            "bm25_active": _bm25 is not None
        }
