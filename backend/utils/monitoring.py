"""
Enhanced monitoring for TiO — tracks retrieval quality, confidence, latency,
hallucination warnings, domain mismatches, and fallback events.

All data is in-memory + JSONL log. No external dependencies.
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
# In-memory store
# ---------------------------------------------------------------------------

_stats: dict[str, Any] = {
    "total_queries": 0,
    "unanswered_queries": 0,        # queries with 0 retrieved chunks
    "fallback_events": 0,           # low-confidence fallbacks triggered
    "hallucination_warnings": 0,    # bracket placeholder detections
    "domain_mismatches": 0,         # session/chatbot domain conflicts
    "weak_grounding_events": 0,     # retrieval confidence < 0.2
    # Orchestration pipeline metrics
    "tavily_triggers": 0,           # times external search was triggered
    "tavily_successes": 0,          # times Tavily returned results
    "context_compressions": 0,      # times context was compressed
    "orchestration_failures": 0,    # prompt build failures
    "prompt_tokens_sum": 0,         # total estimated prompt tokens sent
    "prompt_count": 0,              # prompts generated (for avg calc)
    "intent_counts": Counter(),
    "domain_counts": Counter(),
    "fallback_mode_counts": Counter(),
    "latency_retrieval_ms": deque(maxlen=200),
    "latency_llm_ms": deque(maxlen=200),
    "latency_orchestration_ms": deque(maxlen=200),
    "citation_usage": deque(maxlen=200),
    "confidence_scores": deque(maxlen=200),
    "recent_unanswered": deque(maxlen=50),
    "recent_queries": deque(maxlen=100),
    "recent_fallbacks": deque(maxlen=30),
    "recent_warnings": deque(maxlen=30),
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
    confidence: float = 0.0,
    fallback: bool = False,
    hallucination_warning: bool = False,
    domain_mismatch: bool = False,
    conversation_mode: str = "exploratory",
    # Orchestration pipeline metrics
    tavily_triggered: bool = False,
    tavily_success: bool = False,
    context_compressed: bool = False,
    orchestration_ms: float = 0.0,
    prompt_tokens: int = 0,
) -> None:
    """Non-blocking call — creates an asyncio task for tracking."""
    asyncio.create_task(_async_track(
        query=query,
        intent=intent,
        domain=domain,
        retrieved_chunks=retrieved_chunks,
        retrieval_ms=retrieval_ms,
        llm_ms=llm_ms,
        answered=answered,
        citations=citations or (1 if answered else 0),
        confidence=confidence,
        fallback=fallback,
        hallucination_warning=hallucination_warning,
        domain_mismatch=domain_mismatch,
        conversation_mode=conversation_mode,
        tavily_triggered=tavily_triggered,
        tavily_success=tavily_success,
        context_compressed=context_compressed,
        orchestration_ms=orchestration_ms,
        prompt_tokens=prompt_tokens,
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
    confidence: float,
    fallback: bool,
    hallucination_warning: bool,
    domain_mismatch: bool,
    conversation_mode: str,
    tavily_triggered: bool = False,
    tavily_success: bool = False,
    context_compressed: bool = False,
    orchestration_ms: float = 0.0,
    prompt_tokens: int = 0,
) -> None:
    global _stats
    _stats["total_queries"] += 1
    _stats["intent_counts"][intent] += 1
    _stats["domain_counts"][domain] += 1
    _stats["fallback_mode_counts"][conversation_mode] += 1
    _stats["latency_retrieval_ms"].append(round(retrieval_ms, 1))
    _stats["latency_llm_ms"].append(round(llm_ms, 1))
    _stats["citation_usage"].append(citations)
    _stats["confidence_scores"].append(round(confidence, 3))

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
        "confidence": round(confidence, 3),
        "fallback": fallback,
        "hallucination_warning": hallucination_warning,
        "domain_mismatch": domain_mismatch,
        "conversation_mode": conversation_mode,
    }
    _stats["recent_queries"].append(event)

    # Unanswered
    if not answered or retrieved_chunks == 0:
        _stats["unanswered_queries"] += 1
        _stats["recent_unanswered"].append(query[:120])
        logger.info(
            f"[MONITORING] Unanswered — intent={intent} domain={domain} "
            f"chunks={retrieved_chunks} query={query[:80]!r}"
        )

    # Fallback triggered
    if fallback:
        _stats["fallback_events"] += 1
        _stats["recent_fallbacks"].append({"query": query[:120], "domain": domain, "intent": intent})
        logger.info(f"[MONITORING] Fallback triggered — confidence={confidence:.2f} query={query[:80]!r}")

    # Hallucination warning
    if hallucination_warning:
        _stats["hallucination_warnings"] += 1
        _stats["recent_warnings"].append({"type": "hallucination", "query": query[:120]})
        logger.warning(f"[MONITORING] Hallucination warning — query={query[:80]!r}")

    # Domain mismatch
    if domain_mismatch:
        _stats["domain_mismatches"] += 1
        _stats["recent_warnings"].append({"type": "domain_mismatch", "query": query[:120], "domain": domain})

    # Weak grounding
    if confidence < 0.2 and retrieved_chunks < 3:
        _stats["weak_grounding_events"] += 1

    # Orchestration pipeline metrics
    if tavily_triggered:
        _stats["tavily_triggers"] += 1
    if tavily_success:
        _stats["tavily_successes"] += 1
    if context_compressed:
        _stats["context_compressions"] += 1
    if orchestration_ms > 0:
        _stats["latency_orchestration_ms"].append(round(orchestration_ms, 1))
    if prompt_tokens > 0:
        _stats["prompt_tokens_sum"] += prompt_tokens
        _stats["prompt_count"] += 1

    # Fire-and-forget log append
    await asyncio.to_thread(_append_log, event)


def _append_log(event: dict) -> None:
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except Exception as e:
        logger.warning(f"[MONITORING] Log write failed: {e}")


# ---------------------------------------------------------------------------
# Stats snapshot — used by /admin/monitoring endpoint
# ---------------------------------------------------------------------------

def _avg(values: deque) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 1)


def get_stats_snapshot() -> dict:
    total = _stats["total_queries"]
    prompt_count = _stats["prompt_count"]
    return {
        "total_queries": total,
        "unanswered_queries": _stats["unanswered_queries"],
        "fallback_events": _stats["fallback_events"],
        "hallucination_warnings": _stats["hallucination_warnings"],
        "domain_mismatches": _stats["domain_mismatches"],
        "weak_grounding_events": _stats["weak_grounding_events"],
        "answer_rate_pct": (
            round((1 - _stats["unanswered_queries"] / total) * 100, 1)
            if total > 0 else 100.0
        ),
        "avg_confidence": _avg(_stats["confidence_scores"]),
        "avg_retrieval_ms": _avg(_stats["latency_retrieval_ms"]),
        "avg_llm_ms": _avg(_stats["latency_llm_ms"]),
        "avg_orchestration_ms": _avg(_stats["latency_orchestration_ms"]),
        "avg_citations_per_query": _avg(_stats["citation_usage"]),
        "avg_prompt_tokens": (
            round(_stats["prompt_tokens_sum"] / prompt_count)
            if prompt_count > 0 else 0
        ),
        # Orchestration pipeline health
        "tavily_triggers": _stats["tavily_triggers"],
        "tavily_successes": _stats["tavily_successes"],
        "context_compressions": _stats["context_compressions"],
        "orchestration_failures": _stats["orchestration_failures"],
        "popular_intents": dict(_stats["intent_counts"].most_common(10)),
        "domain_distribution": dict(_stats["domain_counts"].most_common()),
        "conversation_modes": dict(_stats["fallback_mode_counts"].most_common()),
        "recent_unanswered": list(_stats["recent_unanswered"])[-10:],
        "recent_fallbacks": list(_stats["recent_fallbacks"])[-10:],
        "recent_warnings": list(_stats["recent_warnings"])[-10:],
        "recent_queries": list(_stats["recent_queries"])[-20:],
    }
