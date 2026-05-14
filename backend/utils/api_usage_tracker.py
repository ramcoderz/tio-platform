"""
API Usage Tracker for TiO.
Lightweight in-memory counters for all external/internal API calls.
Thread-safe. No external dependencies.
"""

import time
import threading
from collections import defaultdict, deque
from typing import Literal

_lock = threading.Lock()

# Counters
_counters: dict[str, int] = {
    "ollama_requests": 0,
    "gemini_requests": 0,
    "openrouter_requests": 0,
    "tavily_requests": 0,
    "embedding_requests": 0,
    "reranker_requests": 0,
    "llm_total_requests": 0,
    "total_tokens_estimated": 0,
}

# Rolling window of recent calls (last 200)
_recent_calls: deque = deque(maxlen=200)

# Per-minute bucketed rates (last 60 minutes)
_minute_buckets: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))


def track_api_call(
    provider: Literal["ollama", "gemini", "openrouter", "tavily", "embedding", "reranker"],
    tokens: int = 0,
) -> None:
    """
    Non-blocking API call tracker.
    Call this whenever an external/internal API is invoked.
    """
    with _lock:
        minute_bucket = int(time.time()) // 60
        
        if provider == "ollama":
            _counters["ollama_requests"] += 1
            _counters["llm_total_requests"] += 1
            _minute_buckets[minute_bucket]["ollama"] += 1
        elif provider == "gemini":
            _counters["gemini_requests"] += 1
            _counters["llm_total_requests"] += 1
            _minute_buckets[minute_bucket]["gemini"] += 1
        elif provider == "openrouter":
            _counters["openrouter_requests"] += 1
            _counters["llm_total_requests"] += 1
            _minute_buckets[minute_bucket]["openrouter"] += 1
        elif provider == "tavily":
            _counters["tavily_requests"] += 1
            _minute_buckets[minute_bucket]["tavily"] += 1
        elif provider == "embedding":
            _counters["embedding_requests"] += 1
            _minute_buckets[minute_bucket]["embedding"] += 1
        elif provider == "reranker":
            _counters["reranker_requests"] += 1
            _minute_buckets[minute_bucket]["reranker"] += 1

        if tokens > 0:
            _counters["total_tokens_estimated"] += tokens

        _recent_calls.append({
            "ts": round(time.time()),
            "provider": provider,
            "tokens": tokens,
        })

        # Prune old minute buckets (keep last 60)
        cutoff = minute_bucket - 60
        for old_key in [k for k in _minute_buckets if k < cutoff]:
            del _minute_buckets[old_key]


def get_api_usage_snapshot() -> dict:
    """Returns current API usage counters + rate info."""
    with _lock:
        now_bucket = int(time.time()) // 60
        last_minute = dict(_minute_buckets.get(now_bucket, {}))
        last_5min: dict[str, int] = defaultdict(int)
        for bkt in range(now_bucket - 5, now_bucket + 1):
            for provider, count in _minute_buckets.get(bkt, {}).items():
                last_5min[provider] += count

        return {
            "totals": dict(_counters),
            "last_minute": last_minute,
            "last_5_minutes": dict(last_5min),
            "recent_calls": list(_recent_calls)[-30:],
        }
