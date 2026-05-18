from pathlib import Path
from threading import Lock
import time
import faiss
import chromadb
from chromadb.api.models.Collection import Collection
import numpy as np
from rank_bm25 import BM25Okapi
import asyncio
import logging

logger = logging.getLogger(__name__)
from backend.utils.console import console

from backend.rag.embeddings import embed, rerank
from backend.rag.types import RetrievedChunk
from backend.config.settings import get_settings

settings = get_settings()
Path(settings.chroma_dir).mkdir(parents=True, exist_ok=True)

# State
_faiss = faiss.IndexFlatIP(384)
_rows: list[dict] = []
_chroma_client = chromadb.PersistentClient(path=settings.chroma_dir)
_chroma_collections: dict[str, Collection] = {}
_lock = Lock()

def _tokenize(text: str) -> list[str]:
    return text.lower().split()

def _reload_from_chroma() -> None:
    global _faiss, _rows
    try:
        collections = _chroma_client.list_collections()
        with _lock:
            _faiss = faiss.IndexFlatIP(384)
            _rows = []
            
            for coll in collections:
                # Load each collection
                count = coll.count()
                if count == 0: continue
                
                result = coll.get(include=["embeddings", "documents", "metadatas"])
                ids = result.get("ids", [])
                embeddings = result.get("embeddings", [])
                documents = result.get("documents", [])
                metadatas = result.get("metadatas", [])
                
                if ids is None or len(ids) == 0: continue
                if embeddings is None or len(embeddings) == 0: continue
                
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

def _get_collection_for_chatbot(chatbot_id: int) -> Collection:
    import sqlite3
    try:
        # Extract direct file path from sqlite+aiosqlite:/// URL
        db_path = settings.sqlite_url.replace("sqlite+aiosqlite:///", "")
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT is_permanent, name FROM chatbots WHERE id=?", (chatbot_id,))
        row = c.fetchone()
        conn.close()
    except Exception as e:
        logger.warning(f"[VECTORSTORE] Failed to query sqlite database directly for chatbot_id={chatbot_id}: {e}")
        row = None
        
    is_permanent = row[0] if row else False
    name = row[1] if row else "unknown"

    if is_permanent:
        safe_name = "".join(c if c.isalnum() else "_" for c in name.lower())
        coll_name = f"{safe_name}_collection"
    else:
        coll_name = "tio_chunks"
        
    if coll_name not in _chroma_collections:
        _chroma_collections[coll_name] = _chroma_client.get_or_create_collection(coll_name)
    return _chroma_collections[coll_name]


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
            console.error(f"Chunk {c.get('chunk_id')} has empty text, skipping.", stage="INDEXING")
            continue
        valid_chunks.append(c)

    if not valid_chunks:
        logger.error("[VECTORSTORE] No valid chunks remaining after validation.")
        return

    import time
    t_start = time.monotonic()
    print("========================================================", flush=True)
    print("[EMBEDDING]", flush=True)
    print("Generating embeddings...\n", flush=True)
    
    total = len(valid_chunks)
    for idx in range(1, min(total + 1, 6)):
        print("[EMBEDDING]", flush=True)
        print("Chunk:", flush=True)
        print(f"{idx}/{total}\n", flush=True)
    if total > 5:
        print("[EMBEDDING]", flush=True)
        print("Chunk:", flush=True)
        print("...\n", flush=True)
        print("[EMBEDDING]", flush=True)
        print("Chunk:", flush=True)
        print(f"{total}/{total}\n", flush=True)

    vectors = embed([c["text"] for c in valid_chunks])
    if len(vectors) != len(valid_chunks):
        logger.error(f"[VECTORSTORE] Embedding count ({len(vectors)}) != Chunk count ({len(valid_chunks)})")
        raise ValueError("Embedding generation mismatch")

    print("[EMBEDDING]", flush=True)
    print("Completed:", flush=True)
    print(f"{total} embeddings\n", flush=True)
    print("Time:", flush=True)
    print(f"{time.monotonic() - t_start:.1f}s\n", flush=True)

    with _lock:
        try:
            _faiss.add(np.asarray(vectors, dtype="float32"))
            for chunk, vector in zip(valid_chunks, vectors):
                row = dict(chunk)
                row["embedding"] = vector.tolist() if hasattr(vector, "tolist") else list(vector)
                _rows.append(row)


            # Group chunks by chatbot_id to get correct collection
            from collections import defaultdict
            chunks_by_bot = defaultdict(list)
            for c in valid_chunks:
                bot_id = c.get("metadata", {}).get("chatbot_id", 0)
                chunks_by_bot[bot_id].append(c)

            for bot_id, bot_chunks in chunks_by_bot.items():
                coll = _get_collection_for_chatbot(bot_id)
                
                safe_metadatas = []
                for c in bot_chunks:
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
                
                # We need the vectors corresponding to these bot_chunks
                bot_vectors = [vectors[valid_chunks.index(c)] for c in bot_chunks]
                    
                coll.upsert(
                    ids=[c["chunk_id"] for c in bot_chunks],
                    embeddings=[v.tolist() if hasattr(v, "tolist") else list(v) for v in bot_vectors],
                    documents=[c["text"] for c in bot_chunks],
                    metadatas=safe_metadatas,
                )
                print("========================================================", flush=True)
                print("[INDEXING]", flush=True)
                print("Updating vector database...\n", flush=True)
                print("[INDEXING]", flush=True)
                print("Stored:", flush=True)
                print(f"{len(bot_chunks)} vectors\n", flush=True)
                print("[INDEXING]", flush=True)
                print("Collection:", flush=True)
                print(f"{coll.name}\n", flush=True)
            console.info(f"Upserted {len(valid_chunks)} chunks to FAISS & ChromaDB.", stage="INDEXING")
        except Exception as e:
            console.error(f"Vector insertion failed: {e}", stage="INDEXING")
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

def retrieve(
    query: str, 
    top_k: int | None = None, 
    chatbot_id: int | None = None, 
    domain: str | None = None,
    active_entities: list[str] | None = None
) -> list[RetrievedChunk]:
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
        
        # 1. Intent-Aware Priority Boosting
        profile_query_kws = {"experience", "worked", "career", "qualifications", "credentials", "publications", "resume", "cv", "faculty", "staff", "hod"}
        is_profile_search = any(kw in query.lower() for kw in profile_query_kws)
        
        dense_res = _dense_search(q_vec, candidates)
        sparse_res = sorted(_sparse_search(q_tokens, candidates), key=lambda x: x[0], reverse=True)
        
        fused = []
        for row in candidates:
            cid = row["chunk_id"]
            meta = row.get("metadata", {})
            
            d_rank = next((i for i, (_, r) in enumerate(dense_res) if r["chunk_id"] == cid), None)
            s_rank = next((i for i, (_, r) in enumerate(sparse_res) if r["chunk_id"] == cid), None)
            
            # Base RRF score
            score = _compute_rrf([d_rank + 1] if d_rank is not None else [], [s_rank + 1] if s_rank is not None else [])
            
            # 2. Document-Aware Boosting
            if score > 0:
                # Profile/CV/PDF boost (Part 9)
                if meta.get("is_profile_doc"):
                    score *= 1.5
                    if meta.get("source_type") in ("application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"):
                        score *= 1.2 # Extra boost for actual files over profile pages
                
                # Section-Aware boost (Part 8)
                if is_profile_search and meta.get("section_title"):
                    sect = meta.get("section_title", "").lower()
                    if any(kw in sect for kw in profile_query_kws):
                        score *= 1.8 # Heavy boost for matching sections (Work Experience, etc.)

                # Entity grounding boost (Part 10)
                if active_entities:
                    doc_ents = meta.get("entities", [])
                    if isinstance(doc_ents, str): doc_ents = doc_ents.split(", ")
                    if any(e.lower() in [ae.lower() for ae in active_entities] for e in doc_ents):
                        score *= 1.3

                fused.append((score, row))
        
        fused = sorted(fused, key=lambda x: x[0], reverse=True)[:limit]
        return [RetrievedChunk(r["chunk_id"], r["text"], float(s), r["document"], r["metadata"]) for s, r in fused]

from backend.utils.entities import get_query_entities

async def async_retrieve(
    query: str, 
    top_k: int | None = None, 
    chatbot_id: int | None = None, 
    domain: str | None = None,
    workflow: str | None = None,
    active_entities: list[str] | None = None,
    user_goal: str | None = None
) -> list[RetrievedChunk]:
    print(flush=True)
    print("========================================================", flush=True)
    print("[RETRIEVAL]", flush=True)
    print("Searching vectorstore...", flush=True)
    print("========================================================", flush=True)
    print("[RETRIEVAL] Query:", flush=True)
    print(f"{query}\n", flush=True)
    if chatbot_id:
        print("[RETRIEVAL] Chatbot ID:", flush=True)
        print(f"{chatbot_id}\n", flush=True)
    if domain:
        print("[RETRIEVAL] Domain Locking:", flush=True)
        print(f"{domain}\n", flush=True)

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
    try:
        async with asyncio.timeout(5.0):
            dense_res, sparse_res_unsorted = await asyncio.gather(dense_task, sparse_task)
    except TimeoutError:
        logger.error("[RETRIEVAL] Hybrid search timed out after 5.0 seconds.")
        return []
    sparse_res = sorted(sparse_res_unsorted, key=lambda x: x[0], reverse=True)
    
    # --- Query Analysis ---
    q_lower = query.lower()
    q_entities = get_query_entities(query)  # spaCy NER + heuristic names

    if q_entities:
        print("[ENTITY]", flush=True)
        print("Resolved:", flush=True)
        for ent in q_entities:
            print(ent, flush=True)
        print(flush=True)

    # Detect profile/resume intent keywords in query
    _PROFILE_INTENT_KEYWORDS = {
        "resume", "cv", "curriculum", "vitae", "credentials", "experience",
        "qualification", "qualifications", "publications", "worked", "work history",
        "employment", "career", "profile", "biography", "bio", "education", "degree",
        "research", "projects", "achievements", "department", "faculty", "staff", "professor",
        "who is", "about", "contact", "background", "expertise"
    }
    is_profile_query = any(kw in q_lower for kw in _PROFILE_INTENT_KEYWORDS)

    # Profile section keywords for section-aware boosting
    _SECTION_BOOST_WORDS = {
        "experience", "work history", "employment", "career",
        "qualification", "publications", "research", "education", "projects",
        "honors", "awards", "teaching", "grants", "patents", "summary", "bio"
    }

    fused = []
    for row in candidates:
        cid = row["chunk_id"]
        d_rank = next((i for i, (_, r) in enumerate(dense_res) if r["chunk_id"] == cid), None)
        s_rank = next((i for i, (_, r) in enumerate(sparse_res) if r["chunk_id"] == cid), None)
        
        score = _compute_rrf([d_rank + 1] if d_rank is not None else [], [s_rank + 1] if s_rank is not None else [])

        meta = row.get("metadata", {}) or {}
        chunk_lower = row["text"].lower()

        # ---- ENTITY BOOSTING ----
        # Exact entity name match in chunk (strongest signal)
        for ent in q_entities:
            ent_lower = ent.lower()
            if len(ent_lower) > 2:
                if ent_lower in chunk_lower:
                    score += 0.50  # Increased from 0.35 — Exact name match
                elif any(part in chunk_lower for part in ent_lower.split() if len(part) > 3):
                    score += 0.20  # Increased from 0.15 — Partial name match

        # Stored entity metadata match
        stored_entities = meta.get("entities", [])
        if isinstance(stored_entities, list):
            for ent in stored_entities:
                if str(ent).lower() in q_lower:
                    score += 0.25  # Increased from 0.20

        # ---- PROFILE DOCUMENT PRIORITIZATION ----
        is_profile_doc = meta.get("is_profile_doc", False) or "resume" in str(meta.get("document", "")).lower() or "cv" in str(meta.get("document", "")).lower()
        source_type = meta.get("source_type", "")
        section_title = (meta.get("section_title") or "").lower()

        if is_profile_query:
            # Boost PDF/DOCX profile documents heavily
            if source_type in ("application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"):
                score += 0.60  # Increased from 0.40
            elif is_profile_doc:
                score += 0.40  # Increased from 0.25

            # Boost chunks from relevant profile sections
            if section_title and any(kw in section_title for kw in _SECTION_BOOST_WORDS):
                score += 0.45  # Increased from 0.30

            # Penalize generic homepage / nav chunks when profile query
            priority = meta.get("priority", 1)
            if priority <= 1 and not is_profile_doc:
                score -= 0.15  # Increased penalty from 0.10

        # ---- STANDARD PRIORITY BOOSTING ----
        priority = meta.get("priority", 1)
        if priority >= 4:   # profile priority
            score += (priority - 3) * 0.15 # Increased from 0.08
        elif priority == 3: # homepage
            score += 0.05   # Increased from 0.03
        elif priority == 2: # high-quality
            score += 0.03   # Increased from 0.02

        # ---- WORKFLOW BOOSTING ----
        if workflow_tokens:
            for wt in workflow_tokens:
                if len(wt) > 3 and wt in chunk_lower:
                    score += 0.10

        # ---- ACTIVE ENTITY BOOSTING ----
        if active_entities:
            for ent in active_entities:
                if ent.lower() in chunk_lower:
                    score += 0.10

        # ---- USER GOAL ALIGNMENT ----
        if user_goal:
            goal_tokens = _tokenize(user_goal)
            chunk_tokens = _tokenize(row["text"])
            overlap = len(set(goal_tokens) & set(chunk_tokens))
            if overlap > 1:
                score += 0.05 * min(overlap, 3)

        if score > 0:
            fused.append((score, row))
            
    fused = sorted(fused, key=lambda x: x[0], reverse=True)[:20]

    if not fused:
        logger.warning(f"[RETRIEVAL] RRF fusion returned 0 results for query={query!r} chatbot_id={chatbot_id}")
        return []

    results = []
    rerank_activated = False

    if len(fused) > 5 and len(query.split()) > 3:
        try:
            print("[RETRIEVAL]", flush=True)
            print("Found:", flush=True)
            print(f"{len(fused)} candidate chunks\n", flush=True)
            
            t_rerank_start = time.monotonic()
            texts = [r["text"] for _, r in fused]
            
            async with asyncio.timeout(3.0):
                scores = await asyncio.to_thread(rerank, query, texts)
                
            reranked = sorted([(s, r) for s, (_, r) in zip(scores, fused)], key=lambda x: x[0], reverse=True)[:limit]
            
            duration = time.monotonic() - t_rerank_start
            if reranked:
                top_score = reranked[0][0]
                print("[RERANK]", flush=True)
                print("Top rerank score:", flush=True)
                print(f"{top_score:.2f}\n", flush=True)
            
            results = [RetrievedChunk(r["chunk_id"], r["text"], float(s), r["document"], r["metadata"]) for s, r in reranked]
            rerank_activated = True
        except Exception as e:
            print("========================================================", flush=True)
            print("[RETRIEVAL] WARNING", flush=True)
            print(f"Reranking failed or timed out, falling back to RRF: {e}", flush=True)
            print("========================================================", flush=True)
            logger.warning(f"[RETRIEVAL] Reranking failed or timed out, falling back to RRF: {e}")

    if not results:
        results = [RetrievedChunk(r["chunk_id"], r["text"], float(s), r["document"], r["metadata"]) for s, r in fused[:limit]]

    if results:
        avg_score = sum(r.score for r in results) / len(results)
        print("========================================================", flush=True)
        print("[SUCCESS] Retrieval Complete", flush=True)
        print("========================================================", flush=True)
        print("[RETRIEVAL]", flush=True)
        print("Chunks retrieved:", flush=True)
        print(f"{len(results)}\n", flush=True)
        print("[RETRIEVAL]", flush=True)
        print("Average relevance score:", flush=True)
        print(f"{avg_score:.3f}\n", flush=True)
        print("[RETRIEVAL]", flush=True)
        print("Reranking activated:", flush=True)
        print(f"{rerank_activated}\n", flush=True)

    return results

def delete_chatbot_vectors(chatbot_id: int) -> None:
    global _rows, _faiss
    with _lock:
        to_delete = [r["chunk_id"] for r in _rows if r.get("metadata", {}).get("chatbot_id") == chatbot_id]
        if not to_delete: return
        
        _rows = [r for r in _rows if r.get("metadata", {}).get("chatbot_id") != chatbot_id]
        try:
            coll = _get_collection_for_chatbot(chatbot_id)
            coll.delete(ids=to_delete)
        except Exception:
            pass
        _faiss = faiss.IndexFlatIP(384)
        if _rows:
            _faiss.add(np.asarray([r["embedding"] for r in _rows], dtype="float32"))

def delete_chunk_vectors(chunk_ids: list[str]) -> None:
    global _rows, _faiss
    if not chunk_ids: return
    ids = set(chunk_ids)
    with _lock:
        _rows = [r for r in _rows if r["chunk_id"] not in ids]
        
        # We don't know the chatbot_id for sure, so we delete from all collections
        for coll in _chroma_client.list_collections():
            try:
                coll.delete(ids=list(ids))
            except Exception:
                pass
        _faiss = faiss.IndexFlatIP(384)
        if _rows:
            _faiss.add(np.asarray([r["embedding"] for r in _rows], dtype="float32"))

def purge_all() -> None:
    global _rows, _faiss
    with _lock:
        _rows = []
        _faiss = faiss.IndexFlatIP(384)
        try:
            for coll in _chroma_client.list_collections():
                _chroma_client.delete_collection(name=coll.name)
            _chroma_collections.clear()
        except: pass

def get_stats() -> dict:
    with _lock:
        return {
            "total_chunks": len(_rows),
            "vector_count": _faiss.ntotal,
            "document_count": len(set(r.get("document", "") for r in _rows if r.get("document")))
        }
