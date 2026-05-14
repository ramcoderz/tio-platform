"""
LLM client — Ollama (local) + OpenRouter (cloud fallback) + Web Search augmentation.

Priority order:
  1. Ollama (local, private)
  2. OpenRouter (cloud, if Ollama offline or missing model)

Web Search augmentation (Task 19):
  - When retrieval confidence is LOW (< 0.25), the orchestrator can call
    web_search_for_context() to fetch live web results as additional context.
  - This is a RETRIEVAL augmentation, not an LLM replacement.
  - Results are injected into the prompt as additional context, clearly labelled.
  - Uses DuckDuckGo Instant Answer API (no API key required) + httpx scraping.

Alternative LLMs (Task 20):
  - OpenRouter: set OPENROUTER_API_KEY + OPENROUTER_MODEL in .env
    Supports: anthropic/claude-3-haiku, google/gemini-flash-1.5, mistralai/mistral-7b-instruct, etc.
  - Gemini: use backend/llm/gemini_client.py (already exists)
  - Recommendation: For production, use OpenRouter with claude-3-haiku or gemini-flash-1.5
    as the cloud fallback — much higher quality than local llama3 for complex queries.
"""

import httpx
import json
import asyncio
import time
import logging
import re

logger = logging.getLogger(__name__)
from backend.config.settings import get_settings


# ---------------------------------------------------------------------------
# Web Search (DuckDuckGo — no API key needed)
# ---------------------------------------------------------------------------

async def web_search_for_context(query: str, max_results: int = 3) -> str:
    """
    Fetch web search results for a query and return as a context string.
    Uses DuckDuckGo Instant Answer API + lightweight snippet scraping.
    Returns empty string on failure — never raises.
    """
    try:
        encoded = query.replace(" ", "+")
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"

        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                return ""

            data = resp.json()
            snippets = []

            # Abstract (best result)
            abstract = data.get("Abstract", "").strip()
            abstract_url = data.get("AbstractURL", "")
            if abstract:
                snippets.append(f"[Web: {abstract_url}]\n{abstract}")

            # Related topics
            for topic in data.get("RelatedTopics", [])[:max_results]:
                if isinstance(topic, dict):
                    text = topic.get("Text", "").strip()
                    first_url = topic.get("FirstURL", "")
                    if text and len(text) > 30:
                        snippets.append(f"[Web: {first_url}]\n{text}")

            if not snippets:
                return ""

            context = "\n\n".join(snippets[:max_results + 1])
            logger.info(f"[WEB SEARCH] Found {len(snippets)} results for: {query!r}")
            return f"[LIVE WEB RESULTS — use for general knowledge, prefer indexed content for site-specific facts]\n\n{context}"

    except Exception as e:
        logger.warning(f"[WEB SEARCH] Failed for query={query!r}: {e}")
        return ""


# ---------------------------------------------------------------------------
# Ollama Client
# ---------------------------------------------------------------------------

class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434", timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
        self._health_cache = {"checked_at": 0.0, "ok": False}
        self.settings = get_settings()

    async def is_available(self) -> bool:
        now = time.time()
        if now - self._health_cache["checked_at"] < 15:
            return bool(self._health_cache["ok"])
        try:
            res = await self.client.get(f"{self.base_url}/api/tags", timeout=5)
            ok = res.status_code == 200
        except Exception:
            ok = False
        self._health_cache["checked_at"] = now
        self._health_cache["ok"] = ok
        return ok

    async def has_model(self, model: str) -> bool:
        try:
            res = await self.client.get(f"{self.base_url}/api/tags", timeout=5)
            if res.status_code != 200:
                return False
            data = res.json()
            models = [m["name"] for m in data.get("models", [])]
            return any(m.startswith(model) for m in models)
        except Exception:
            return False

    # --- OpenRouter fallback ---

    async def _openrouter_generate_stream(self, prompt: str):
        if not self.settings.openrouter_api_key:
            yield (
                "Ollama is offline and no OpenRouter API key is configured. "
                "Set OPENROUTER_API_KEY in your .env file to enable cloud LLM fallback. "
                "Supported models include: anthropic/claude-3-haiku, google/gemini-flash-1.5, mistralai/mistral-7b-instruct."
            )
            return

        url = f"{self.settings.openrouter_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "TiO"
        }
        payload = {
            "model": self.settings.openrouter_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
        }
        try:
            async with self.client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            data = json.loads(line[6:])
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            yield f"\n[OpenRouter Error: {e}]"

    async def _openrouter_generate(self, prompt: str) -> str:
        if not self.settings.openrouter_api_key:
            return (
                "Ollama is offline and no OpenRouter API key is configured. "
                "Set OPENROUTER_API_KEY in your .env file to enable cloud LLM fallback. "
                "Supported models: anthropic/claude-3-haiku, google/gemini-flash-1.5, mistralai/mistral-7b-instruct."
            )
        url = f"{self.settings.openrouter_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.openrouter_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        try:
            res = await self.client.post(url, headers=headers, json=payload)
            res.raise_for_status()
            return res.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"[OpenRouter Error: {e}]"

    # --- Main generation methods ---

    async def generate_stream(self, prompt: str, model: str = "llama3"):
        if not await self.is_available() or not await self.has_model(model):
            logger.info("[LLM] Ollama unavailable — routing to OpenRouter fallback")
            async for chunk in self._openrouter_generate_stream(prompt):
                yield chunk
            return

        url = f"{self.base_url}/api/generate"
        payload = {"model": model, "prompt": prompt, "stream": True}
        logger.debug(f"[LLM] Ollama stream: model={model}")

        try:
            async with self.client.stream("POST", url, json=payload) as response:
                if response.status_code == 404:
                    yield f"Model '{model}' not found. Run: ollama pull {model}"
                    return
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if "response" in data:
                            yield data["response"]
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"[LLM] Ollama stream error: {e} — attempting OpenRouter")
            async for chunk in self._openrouter_generate_stream(prompt):
                yield chunk

    async def generate(self, prompt: str, model: str = "llama3") -> str:
        if not await self.is_available() or not await self.has_model(model):
            logger.info("[LLM] Ollama unavailable — routing to OpenRouter fallback")
            return await self._openrouter_generate(prompt)

        url = f"{self.base_url}/api/generate"
        payload = {"model": model, "prompt": prompt, "stream": False}
        try:
            res = await self.client.post(url, json=payload)
            res.raise_for_status()
            return res.json().get("response", "")
        except Exception as e:
            logger.warning(f"[LLM] Ollama generate failed: {e} — trying OpenRouter")
            return await self._openrouter_generate(prompt)

    def get_llm_info(self) -> dict:
        """Return current LLM configuration for monitoring."""
        return {
            "local_model": self.settings.ollama_model,
            "ollama_url": self.base_url,
            "openrouter_configured": bool(self.settings.openrouter_api_key),
            "openrouter_model": self.settings.openrouter_model,
            "alternatives": [
                "anthropic/claude-3-haiku (OpenRouter) — best quality",
                "google/gemini-flash-1.5 (OpenRouter) — fast + smart",
                "mistralai/mistral-7b-instruct (OpenRouter) — lightweight",
                "ollama pull phi3 — lightweight local option",
                "ollama pull gemma2 — strong local option",
            ]
        }


ollama_client = OllamaClient()
