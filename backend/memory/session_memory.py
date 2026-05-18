"""
TiO Session Memory Engine — Phase 2: Conversational Intelligence

Tracks per-session state:
  - Active entities (people, orgs, documents)
  - Conversation topics / retrieval domain
  - Document cache (previously retrieved PDFs/adaptive docs)
  - Retrieval cache (reuse vector candidates for repeated queries)
  - Session graph: User → Topics → Entities → Documents → Retrievals

All state is in-memory per process with an optional DB flush path.
"""

import time
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("tio.memory")

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class EntityRecord:
    name: str
    entity_type: str          # PERSON | ORG | DOCUMENT | TOPIC
    mention_count: int = 1
    last_seen: float = field(default_factory=time.monotonic)
    source_docs: list[str] = field(default_factory=list)

@dataclass
class DocumentRecord:
    url: str
    doc_type: str             # "pdf" | "docx" | "html"
    title: str = ""
    chunk_ids: list[str] = field(default_factory=list)
    retrieved_at: float = field(default_factory=time.monotonic)

@dataclass
class RetrievalCacheEntry:
    query_hash: str
    chunks: list          # stores RetrievedChunk objects directly
    entity_key: str       # entity name that drove retrieval
    cached_at: float = field(default_factory=time.monotonic)
    ttl_seconds: float = 300  # 5-minute TTL

    def is_valid(self) -> bool:
        return (time.monotonic() - self.cached_at) < self.ttl_seconds


@dataclass
class SessionState:
    session_id: str
    chatbot_id: int

    # Entity tracking
    entities: dict[str, EntityRecord] = field(default_factory=dict)

    # Topic / domain tracking
    topics: deque = field(default_factory=lambda: deque(maxlen=10))
    current_domain: str = "general"
    current_topic: str = ""

    # Document memory
    documents: dict[str, DocumentRecord] = field(default_factory=dict)

    # Retrieval cache (query_hash → CacheEntry)
    retrieval_cache: dict[str, RetrievalCacheEntry] = field(default_factory=dict)

    # Session graph edges (simple adjacency list)
    graph: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    # Message count for decay calculations
    message_count: int = 0
    created_at: float = field(default_factory=time.monotonic)


# ---------------------------------------------------------------------------
# In-memory session registry
# ---------------------------------------------------------------------------

_sessions: dict[str, SessionState] = {}
_MAX_SESSIONS = 500  # LRU eviction above this

def _evict_oldest():
    if len(_sessions) <= _MAX_SESSIONS:
        return
    oldest_key = min(_sessions, key=lambda k: _sessions[k].created_at)
    del _sessions[oldest_key]
    logger.debug(f"[MEMORY] Evicted oldest session: {oldest_key}")


def get_session(session_id: str, chatbot_id: int) -> SessionState:
    """Get or create a session state object."""
    key = f"{session_id}:{chatbot_id}"
    if key not in _sessions:
        _evict_oldest()
        _sessions[key] = SessionState(session_id=session_id, chatbot_id=chatbot_id)
        logger.debug(f"[MEMORY] New session created: {key}")
    return _sessions[key]


def clear_session(session_id: str, chatbot_id: int):
    key = f"{session_id}:{chatbot_id}"
    _sessions.pop(key, None)


# ---------------------------------------------------------------------------
# Entity tracking
# ---------------------------------------------------------------------------

def update_entities(state: SessionState, entities: list[str], entity_type: str = "PERSON"):
    """Add or update entity records from the latest query."""
    for name in entities:
        if not name.strip():
            continue
        key = name.lower().strip()
        if key in state.entities:
            state.entities[key].mention_count += 1
            state.entities[key].last_seen = time.monotonic()
        else:
            state.entities[key] = EntityRecord(
                name=name,
                entity_type=entity_type,
            )
        # Graph edge: session → entity
        if name not in state.graph["__session__"]:
            state.graph["__session__"].append(name)

    if entities:
        _print_memory_telemetry("Current entity", entities[0])


def get_active_entities(state: SessionState, top_k: int = 5) -> list[str]:
    """Return the most recently-mentioned entities."""
    sorted_ents = sorted(
        state.entities.values(),
        key=lambda e: (e.mention_count * 0.4 + (1.0 / max(time.monotonic() - e.last_seen, 1)) * 0.6),
        reverse=True
    )
    return [e.name for e in sorted_ents[:top_k]]


# ---------------------------------------------------------------------------
# Topic / domain memory
# ---------------------------------------------------------------------------

def update_topic(state: SessionState, topic: str, domain: str):
    """Track the current conversation topic."""
    state.current_domain = domain
    if topic and topic != state.current_topic:
        state.current_topic = topic
        state.topics.appendleft(topic)
        _print_memory_telemetry("Conversation topic", topic)

    # Graph edge: entity → topic
    active = get_active_entities(state, top_k=1)
    if active and topic:
        if topic not in state.graph[active[0]]:
            state.graph[active[0]].append(topic)


# ---------------------------------------------------------------------------
# Document memory
# ---------------------------------------------------------------------------

def register_document(state: SessionState, url: str, doc_type: str, title: str = "", chunk_ids: list[str] = None):
    """Register a newly retrieved document in session memory."""
    if url not in state.documents:
        state.documents[url] = DocumentRecord(
            url=url,
            doc_type=doc_type,
            title=title or url.split("/")[-1],
            chunk_ids=chunk_ids or [],
        )
        display_name = title or url.split("/")[-1]
        _print_memory_telemetry("Cached documents", display_name)
        # Graph edge: topic → document
        if state.current_topic and url not in state.graph[state.current_topic]:
            state.graph[state.current_topic].append(url)
    else:
        # Update chunk list
        existing = state.documents[url]
        if chunk_ids:
            existing.chunk_ids = list(set(existing.chunk_ids + chunk_ids))
        existing.retrieved_at = time.monotonic()


def get_cached_documents(state: SessionState, doc_type: str = None) -> list[DocumentRecord]:
    """Return previously registered documents, optionally filtered by type."""
    docs = list(state.documents.values())
    if doc_type:
        docs = [d for d in docs if d.doc_type == doc_type]
    return sorted(docs, key=lambda d: d.retrieved_at, reverse=True)


# ---------------------------------------------------------------------------
# Retrieval cache
# ---------------------------------------------------------------------------

import hashlib

def _query_hash(query: str, entity_key: str) -> str:
    raw = f"{query.lower().strip()}|{entity_key.lower()}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def cache_retrieval(state: SessionState, query: str, entity_key: str, chunks: list[dict]):
    """Store retrieval results for the query/entity combination."""
    h = _query_hash(query, entity_key)
    state.retrieval_cache[h] = RetrievalCacheEntry(
        query_hash=h,
        chunks=chunks,
        entity_key=entity_key,
    )
    # Prune expired entries
    expired = [k for k, v in state.retrieval_cache.items() if not v.is_valid()]
    for k in expired:
        del state.retrieval_cache[k]


def get_cached_retrieval(state: SessionState, query: str, entity_key: str) -> Optional[list[dict]]:
    """Return cached retrieval results if still valid."""
    h = _query_hash(query, entity_key)
    entry = state.retrieval_cache.get(h)
    if entry and entry.is_valid():
        logger.info(f"[MEMORY] Cache HIT for query_hash={h}, entity={entity_key}")
        return entry.chunks
    return None


# ---------------------------------------------------------------------------
# Session graph snapshot
# ---------------------------------------------------------------------------

def get_session_graph(state: SessionState) -> dict:
    """Return a serializable session graph snapshot."""
    return {
        "entities": [
            {
                "name": e.name,
                "type": e.entity_type,
                "mentions": e.mention_count,
            }
            for e in state.entities.values()
        ],
        "topics": list(state.topics),
        "documents": [
            {"url": d.url, "type": d.doc_type, "title": d.title}
            for d in state.documents.values()
        ],
        "current_topic": state.current_topic,
        "current_domain": state.current_domain,
    }


# ---------------------------------------------------------------------------
# Telemetry helpers
# ---------------------------------------------------------------------------

def _print_memory_telemetry(label: str, value: str):
    print(flush=True)
    print("[MEMORY]", flush=True)
    print(f"{label}:", flush=True)
    print(f"{value}\n", flush=True)


def print_session_summary(state: SessionState):
    """Print a full [MEMORY] session summary block to the terminal."""
    active_ents = get_active_entities(state, top_k=3)
    cached_docs = get_cached_documents(state)

    print(flush=True)
    print("========================================================", flush=True)
    print("[MEMORY]", flush=True)
    print("Session Intelligence Summary", flush=True)
    print("========================================================", flush=True)

    if active_ents:
        print("Active entities:", flush=True)
        for e in active_ents:
            print(f"  - {e}", flush=True)
        print(flush=True)

    if state.current_topic:
        print(f"Conversation topic: {state.current_topic}", flush=True)
        print(flush=True)

    if state.current_domain:
        print(f"Retrieval domain: {state.current_domain}", flush=True)
        print(flush=True)

    if cached_docs:
        print("Cached documents:", flush=True)
        for d in cached_docs[:3]:
            print(f"  - {d.title or d.url}", flush=True)
        print(flush=True)

    cache_hits = len(state.retrieval_cache)
    print(f"Retrieval cache entries: {cache_hits}", flush=True)
    print(f"Total messages: {state.message_count}", flush=True)
    print("========================================================", flush=True)
    print(flush=True)
