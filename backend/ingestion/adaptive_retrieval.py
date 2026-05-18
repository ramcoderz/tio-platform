"""
Phase 12B — Adaptive Retrieval & Contextual Knowledge Expansion.

Transforms TiO from static RAG into adaptive contextual intelligence:

  1. Evaluate retrieval quality after initial local search
  2. If insufficient → discover related pages / documents contextually
  3. Async incremental ingestion (never blocks WS / LLM inference)
  4. Second retrieval pass for grounded response

Feature-flagged:
  ENABLE_ADAPTIVE_RETRIEVAL      (bool)
  ENABLE_INCREMENTAL_INGESTION   (bool)
  ENABLE_DYNAMIC_DOC_DISCOVERY   (bool)

Engineering contract:
  - NEVER raises exceptions to the caller
  - NEVER blocks the websocket/LLM streaming loop
  - ALWAYS falls back to existing indexed knowledge on failure
  - Logs every stage clearly with [ADAPTIVE] / [DOC_PARSER] / [EMBEDDING] prefixes
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse, urljoin

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Entity-to-section mapping for document-aware routing
# ---------------------------------------------------------------------------

_ENTITY_KEYWORDS = {
    "experience": ["work experience", "employment", "worked at", "previous role", "career"],
    "qualification": ["qualification", "credentials", "degree", "education", "ph.d", "masters", "b.tech"],
    "publication": ["publication", "paper", "journal", "research paper", "published"],
    "certification": ["certification", "certified", "certificate"],
    "research": ["research", "interest", "specialisation", "focus area"],
}

_PROFILE_TRIGGERS = [
    "faculty", "hod", "head of department", "professor", "dr.", "mr.", "ms.",
    "work experience", "qualification", "resume", "cv", "profile",
    "who is", "tell me about",
]

_DOC_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md"}

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class RetrievalQualityReport:
    """Result of retrieval quality evaluation."""
    is_sufficient: bool
    chunk_count: int
    avg_rerank_score: float
    entity_resolved: bool
    reason: str
    triggered_by: list[str] = field(default_factory=list)


@dataclass
class DiscoveredResource:
    """A URL or doc path discovered during contextual expansion."""
    url: str
    resource_type: str   # "page" | "pdf" | "docx" | "other"
    priority: int = 0    # Higher = more relevant


# ---------------------------------------------------------------------------
# 1. Retrieval Quality Evaluator
# ---------------------------------------------------------------------------

def evaluate_retrieval_quality(
    query: str,
    chunks: list,
    chatbot_base_url: str = "",
) -> RetrievalQualityReport:
    """
    Evaluate whether the current retrieval is sufficient to answer the query.
    Returns a RetrievalQualityReport with is_sufficient=True|False.
    """
    from backend.config.settings import get_settings
    settings = get_settings()

    min_chunks = settings.adaptive_min_chunks
    min_score  = settings.adaptive_min_rerank_score

    chunk_count = len(chunks)
    scores = [getattr(c, "score", 0.0) for c in chunks]
    avg_score = sum(scores) / len(scores) if scores else 0.0
    query_lower = query.lower()

    triggers = []

    if chunk_count < min_chunks:
        triggers.append(f"chunk_count={chunk_count} < min={min_chunks}")
    if avg_score < min_score:
        triggers.append(f"avg_score={avg_score:.3f} < min={min_score}")

    # Entity resolution check: if query names a person/HOD but no chunk contains the name
    is_profile_query = any(kw in query_lower for kw in _PROFILE_TRIGGERS)
    entity_resolved = True
    if is_profile_query and chunks:
        combined = " ".join(getattr(c, "text", "") for c in chunks).lower()
        # Heuristic: look for proper-noun-like tokens (capitalized sequences) in query
        name_candidates = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', query)
        for name in name_candidates:
            if name.lower() not in combined:
                entity_resolved = False
                triggers.append(f"entity_unresolved='{name}'")
                break

    is_sufficient = len(triggers) == 0

    reason = "Retrieval sufficient." if is_sufficient else f"Insufficient: {'; '.join(triggers)}"
    logger.info(f"[ADAPTIVE] Quality eval: sufficient={is_sufficient} | {reason}")

    return RetrievalQualityReport(
        is_sufficient=is_sufficient,
        chunk_count=chunk_count,
        avg_rerank_score=avg_score,
        entity_resolved=entity_resolved,
        reason=reason,
        triggered_by=triggers,
    )


# ---------------------------------------------------------------------------
# 2. Related URL Discovery
# ---------------------------------------------------------------------------

async def discover_related_resources(
    query: str,
    chatbot_base_url: str,
    chatbot_id: int,
    max_resources: int = 5,
) -> list[DiscoveredResource]:
    """
    Discover URLs and documents contextually related to the query.
    Uses lightweight BFS from the chatbot's base URL with keyword scoring.
    Returns at most max_resources items, never raises.
    """
    try:
        from backend.ingestion.scraper import scraper
        import httpx
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin, urlparse

        query_lower = query.lower()
        base_domain = urlparse(chatbot_base_url).netloc.lower()
        resources: list[DiscoveredResource] = []

        logger.info(f"[ADAPTIVE] Discovering related pages for: {query!r} on {chatbot_base_url}")

        # Score keywords extracted from query
        score_terms: list[str] = []
        score_terms += re.findall(r'\b[a-z]{4,}\b', query_lower)  # meaningful words

        # Crawl only the homepage for related links (light touch, no recursive BFS)
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            try:
                resp = await client.get(chatbot_base_url, headers={"User-Agent": "TiO-Adaptive/1.0"})
                if resp.status_code != 200:
                    return resources
                soup = BeautifulSoup(resp.text, "html.parser")
                links = [a.get("href", "") for a in soup.find_all("a", href=True)]
            except Exception as e:
                logger.warning(f"[ADAPTIVE] Homepage fetch failed: {e}")
                return resources

        seen: set[str] = set()
        for raw_link in links:
            try:
                abs_url = urljoin(chatbot_base_url, raw_link)
                parsed = urlparse(abs_url)
                if parsed.netloc.lower() != base_domain:
                    continue
                norm = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
                if norm in seen:
                    continue
                seen.add(norm)

                path_lower = parsed.path.lower()
                ext = "." + path_lower.rsplit(".", 1)[-1] if "." in path_lower else ""
                is_doc = ext in _DOC_EXTENSIONS

                # Score based on query term overlap in URL path
                score = sum(20 for t in score_terms if t in path_lower)
                if is_doc:
                    score += 30
                if any(kw in path_lower for kw in ["profile", "faculty", "staff", "resume", "cv", "hod"]):
                    score += 40

                if score > 0:
                    rtype = "pdf" if ext == ".pdf" else "docx" if ext in {".docx", ".doc"} else "page"
                    resources.append(DiscoveredResource(url=norm, resource_type=rtype, priority=score))
                    
                    if rtype in ("pdf", "docx"):
                        filename = norm.split("/")[-1] or "document"
                        print("[ADAPTIVE]", flush=True)
                        print("Document found:", flush=True)
                        print(f"{filename}\n", flush=True)
                    else:
                        print("[ADAPTIVE]", flush=True)
                        print("Related URL found:", flush=True)
                        path = parsed.path.strip('/') or norm
                        print(f"{path}\n", flush=True)
            except Exception:
                continue

        resources.sort(key=lambda r: r.priority, reverse=True)
        top = resources[:max_resources]
        logger.info(f"[ADAPTIVE] Discovered {len(top)} related resources: {[r.url for r in top]}")
        return top

    except Exception as e:
        logger.warning(f"[ADAPTIVE] Resource discovery failed: {e}")
        return []


# ---------------------------------------------------------------------------
# 3. Incremental Ingestion Pipeline
# ---------------------------------------------------------------------------

async def incremental_ingest(
    resources: list[DiscoveredResource],
    chatbot_id: int,
    domain: str = "general",
) -> int:
    """
    Incrementally ingest a list of discovered resources into the vector store.
    Runs async-safe — never blocks websocket/LLM streams.
    Returns the number of new chunks successfully indexed.
    """
    from backend.ingestion.scraper import scraper
    from backend.ingestion.service import _chunk_text
    from backend.vectorstore.service import upsert_chunks

    total_new = 0

    for resource in resources:
        try:
            print("[DOCUMENT]", flush=True)
            print("Found:", flush=True)
            print(f"{resource.url.split('/')[-1] or resource.url}\n", flush=True)
            logger.info(f"[ADAPTIVE] Incrementally ingesting: {resource.url} ({resource.resource_type})")

            # Extract content based on resource type
            content = await scraper.extract_content(resource.url)
            if not content or len(content.strip()) < 100:
                logger.warning(f"[ADAPTIVE] Skipping {resource.url}: insufficient content ({len(content)} chars)")
                continue

            # Chunk (reuses the stable section-aware chunker)
            chunks = _chunk_text(content, resource.url, chatbot_id, domain=domain)
            if not chunks:
                logger.warning(f"[ADAPTIVE] No chunks generated for {resource.url}")
                continue

            # Upsert into FAISS + ChromaDB (deduplication is handled inside upsert_chunks by chunk_id)
            upsert_chunks(chunks)
            total_new += len(chunks)
            logger.info(f"[ADAPTIVE] +{len(chunks)} new chunks from {resource.url}")

        except Exception as e:
            logger.warning(f"[ADAPTIVE] Incremental ingestion failed for {resource.url}: {e}")
            continue

    logger.info(f"[ADAPTIVE] Incremental ingestion complete. Total new chunks: {total_new}")
    return total_new


# ---------------------------------------------------------------------------
# 4. Adaptive Orchestrator — Main Entry Point
# ---------------------------------------------------------------------------

async def adaptive_retrieve(
    query: str,
    initial_chunks: list,
    chatbot_id: int,
    chatbot_base_url: str,
    domain: str = "general",
    top_k: int = 4,
) -> tuple[list, bool]:
    """
    Main adaptive retrieval entry point.

    Returns:
        (chunks, was_expanded)
        - chunks: best available chunks (initial or post-expansion)
        - was_expanded: True if adaptive expansion was triggered and completed

    Contract:
        - NEVER raises
        - NEVER blocks WS / LLM stream (background async ingestion only)
        - Falls back to initial_chunks on any failure
    """
    from backend.config.settings import get_settings
    settings = get_settings()

    if not settings.enable_adaptive_retrieval:
        return initial_chunks, False

    # Step 1: Evaluate initial retrieval quality
    report = evaluate_retrieval_quality(query, initial_chunks, chatbot_base_url)
    if report.is_sufficient:
        logger.info("[ADAPTIVE] Initial retrieval sufficient. No expansion needed.")
        return initial_chunks, False

    print(flush=True)
    print("========================================================", flush=True)
    print("[ADAPTIVE]", flush=True)
    print("Low retrieval confidence detected", flush=True)
    print("========================================================", flush=True)
    print("[ADAPTIVE]", flush=True)
    print("Searching related pages...\n", flush=True)

    logger.info(f"[ADAPTIVE] Retrieval quality insufficient: {report.reason}")
    logger.info("[ADAPTIVE] Discovering related pages...")

    if not settings.enable_dynamic_doc_discovery:
        return initial_chunks, False

    try:
        # Step 2: Discover related resources
        resources = await discover_related_resources(
            query=query,
            chatbot_base_url=chatbot_base_url,
            chatbot_id=chatbot_id,
            max_resources=4,
        )

        if not resources:
            logger.info("[ADAPTIVE] No related resources found. Using initial chunks.")
            return initial_chunks, False

        if not settings.enable_incremental_ingestion:
            return initial_chunks, False

        print("[ADAPTIVE]", flush=True)
        print("Incremental Ingestion started\n", flush=True)

        # Step 3: Async incremental ingestion
        new_count = await incremental_ingest(resources, chatbot_id, domain)

        if new_count == 0:
            logger.info("[ADAPTIVE] Incremental ingestion yielded no new chunks.")
            return initial_chunks, False

        # Step 4: Second retrieval pass with expanded knowledge
        logger.info(f"[ADAPTIVE] Second retrieval pass after +{new_count} new chunks...")
        from backend.vectorstore.service import async_retrieve
        expanded_chunks = await async_retrieve(
            query=query,
            top_k=top_k,
            chatbot_id=chatbot_id,
            domain=domain,
        )

        # Use expanded if meaningfully better, otherwise keep initial
        if len(expanded_chunks) > len(initial_chunks):
            print("[RETRIEVAL]", flush=True)
            print("Second retrieval pass complete\n", flush=True)
            logger.info(f"[ADAPTIVE] Expanded retrieval successful: {len(expanded_chunks)} chunks (was {len(initial_chunks)})")
            return expanded_chunks, True
        else:
            logger.info("[ADAPTIVE] Expansion did not improve results. Keeping initial.")
            return initial_chunks, False

    except Exception as e:
        logger.warning(f"[ADAPTIVE] Adaptive retrieval failed safely: {e}. Using initial chunks.")
        return initial_chunks, False
