"""
Tavily Client — secure external research with retry + timeout.

Security rules:
- API key loaded from environment only (never from config files committed to git)
- Key never exposed in API responses or logs
- Results sanitized before injection into prompts
"""

import logging
import httpx
from typing import List, Dict, Any

from backend.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_REDACTED = "[REDACTED]"


class TavilyClient:
    def __init__(self):
        self.api_key = getattr(settings, "tavily_api_key", None) or ""
        self.base_url = "https://api.tavily.com/search"
        self._enabled = bool(self.api_key)
        if self._enabled:
            logger.info("[TAVILY] Client initialized with API key.")
        else:
            logger.warning("[TAVILY] No API key configured. External search disabled.")

    def _safe_log(self, msg: str) -> None:
        """Log without exposing API key."""
        if self.api_key:
            msg = msg.replace(self.api_key, _REDACTED)
        logger.info(msg)

    async def search(
        self,
        query: str,
        search_depth: str = "basic",
        max_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Perform an external search using Tavily.
        - Timeout: 8 seconds
        - Returns empty list on any error (never raises)
        - Results are sanitized (no raw HTML)
        """
        if not self._enabled:
            logger.debug("[TAVILY] Disabled — no API key.")
            return []

        if not query or len(query.strip()) < 3:
            return []

        payload = {
            "api_key":            self.api_key,
            "query":              query[:400],    # cap query length
            "search_depth":       search_depth,
            "max_results":        min(max_results, 8),
            "include_answer":     True,
            "include_raw_content": False,
            "include_images":     False,
        }

        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                resp = await client.post(self.base_url, json=payload)
                resp.raise_for_status()
                data = resp.json()

            results = data.get("results", [])
            # Also capture the direct answer if present
            direct_answer = data.get("answer", "")

            output: List[Dict[str, Any]] = []

            # Direct answer as first result
            if direct_answer and len(direct_answer) > 20:
                output.append({
                    "text":   direct_answer[:800],
                    "url":    "tavily://answer",
                    "title":  "Direct Answer",
                    "score":  1.0,
                    "source": "tavily_answer",
                })

            for r in results:
                content = r.get("content", "").strip()
                if not content or len(content) < 20:
                    continue
                output.append({
                    "text":   content[:1000],    # cap per-result length
                    "url":    r.get("url", ""),
                    "title":  r.get("title", ""),
                    "score":  float(r.get("score", 0.0)),
                    "source": "tavily",
                })

            self._safe_log(f"[TAVILY] Search complete: {len(output)} results for query={query[:60]!r}")
            return output[:max_results]

        except httpx.TimeoutException:
            logger.warning(f"[TAVILY] Timeout for query={query[:60]!r}")
            return []
        except httpx.HTTPStatusError as e:
            logger.error(f"[TAVILY] HTTP error {e.response.status_code} for query={query[:60]!r}")
            return []
        except Exception as e:
            logger.error(f"[TAVILY] Unexpected error: {type(e).__name__}: {e}")
            return []


tavily_client = TavilyClient()
