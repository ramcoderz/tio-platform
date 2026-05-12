"""
Lightweight monitoring for TiO.

Tracks:
- Query latency (retrieval + LLM)
- Popular intents / skills
- Unanswered queries (no relevant chunks retrieved)
- Domain distribution

All data is kept in-memory and flushed periodically to a JSON log file.
No fake AI metrics. No speculative scoring.
"""

import asyncio
import json
import logging
import time
from collections import Counter, deque
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory store (lightweight — no Redis dependency)
# ---------------------------------------------------------------------------

_stats: dict[str, Any] = {
    "total_queries": 0,
    "unanswered_queries": 0,        # queries with 0 retrieved chunks
    "intent_counts": Counter(),
    "domain_counts": Counter(),
    "latency_retrieval_ms": deque(maxlen=200),
    "latency_llm_ms": deque(maxlen=200),
    "citation_usage": deque(maxlen=200),
    "recent_unanswered": deque(maxlen=50),   # store raw query text for review
    "recent_queries": deque(maxlen=100),
}

_LOG_PATH = Path("data/monitoring_log.jsonl")


# ---------------------------------------------------------------------------
# Track a single query event
# ---------------------------------------------------------------------------

async def track_query(
    *,
    query: str,
    intent: str,
    domain: str,
    retrieved_chunks: int,
    retrieval_ms: float,
    llm_ms: float,
    answered: bool,
    citations: int = 0,
) -> None:
    """Non-blocking call — runs the actual tracking in a thread."""
    asyncio.create_task(_async_track(
        query=query,
        intent=intent,
        domain=domain,
        retrieved_chunks=retrieved_chunks,
        retrieval_ms=retrieval_ms,
        llm_ms=llm_ms,
        answered=answered,
        citations=citations or (1 if answered else 0),
    ))


async def _async_track(
    *,
    query: str,
    intent: str,
    domain: str,
    retrieved_chunks: int,
    retrieval_ms: float,
    llm_ms: float,
    answered: bool,
    citations: int,
) -> None:
    global _stats
    _stats["total_queries"] += 1
    _stats["intent_counts"][intent] += 1
    _stats["domain_counts"][domain] += 1
    _stats["latency_retrieval_ms"].append(round(retrieval_ms, 1))
    _stats["latency_llm_ms"].append(round(llm_ms, 1))
    _stats["citation_usage"].append(citations)

    event = {
        "ts": round(time.time()),
        "query": query[:120],
        "intent": intent,
        "domain": domain,
        "chunks": retrieved_chunks,
        "citations": citations,
        "retrieval_ms": round(retrieval_ms, 1),
        "llm_ms": round(llm_ms, 1),
        "answered": answered,
    }
    _stats["recent_queries"].append(event)

    if not answered or retrieved_chunks == 0:
        _stats["unanswered_queries"] += 1
        _stats["recent_unanswered"].append(query[:120])
        logger.info(f"[MONITORING] Unanswered query — intent={intent} domain={domain} query={query[:80]!r}")

    # Fire-and-forget append to JSONL log
    await asyncio.to_thread(_append_log, event)


def _append_log(event: dict) -> None:
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except Exception as e:
        logger.warning(f"[MONITORING] Log write failed: {e}")


# ---------------------------------------------------------------------------
# Stats snapshot — used by the /admin/monitoring endpoint
# ---------------------------------------------------------------------------

def _avg(values: deque) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 1)


def get_stats_snapshot() -> dict:
    return {
        "total_queries": _stats["total_queries"],
        "unanswered_queries": _stats["unanswered_queries"],
        "answer_rate_pct": (
            round((1 - _stats["unanswered_queries"] / _stats["total_queries"]) * 100, 1)
            if _stats["total_queries"] > 0 else 100.0
        ),
        "avg_retrieval_ms": _avg(_stats["latency_retrieval_ms"]),
        "avg_llm_ms": _avg(_stats["latency_llm_ms"]),
        "avg_citations_per_query": _avg(_stats["citation_usage"]),
        "popular_intents": dict(_stats["intent_counts"].most_common(10)),
        "domain_distribution": dict(_stats["domain_counts"].most_common()),
        "recent_unanswered": list(_stats["recent_unanswered"])[-10:],
        "recent_queries": list(_stats["recent_queries"])[-20:],
    }
