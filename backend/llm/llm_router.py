"""
TiO Unified LLM Router
======================
Dispatches generate() / generate_stream() to the correct backend
based on settings.llm_provider.

Priority order when ollama is selected but unavailable:
  ollama -> openrouter -> gemini -> fallback string

This is a DROP-IN replacement for direct ollama_client calls.
"""
from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


class LLMRouter:
    """Single entry-point for all LLM generation in TiO."""

    def __init__(self):
        from backend.config.settings import get_settings
        self.settings = get_settings()

    # ------------------------------------------------------------------
    # Public API (mirrors ollama_client interface exactly)
    # ------------------------------------------------------------------

    async def generate(self, prompt: str, model: str | None = None) -> str:
        import time
        from backend.utils.console import console
        provider = self.settings.llm_provider.lower()
        t_start = time.monotonic()

        logger.info(f"[LLM] Starting generation using provider={provider}")
        console.info(f"LLM is working: starting inference with {provider.upper()} local/cloud model...", stage="LLM")

        if provider == "ollama":
            try:
                result = await self._ollama_generate(prompt, model)
                # Graceful fallback if Ollama returned a system-error string
                if result.startswith("[SYSTEM]") or result.startswith("[ERROR]"):
                    logger.warning(f"[LLM] Fallback activation: Ollama returned system-error: {result[:100]}")
                    console.warning("Ollama local connection failed (returned system error). Activating OpenRouter cloud fallback...", stage="FALLBACK")
                    res = await self._openrouter_generate(prompt)
                    duration = time.monotonic() - t_start
                    logger.info(f"[LLM] Inference duration (fallback): {duration:.3f}s")
                    console.success(f"Fallback generation completed successfully in {duration:.3f}s.", stage="FALLBACK")
                    return res
                duration = time.monotonic() - t_start
                logger.info(f"[LLM] Inference duration: {duration:.3f}s")
                console.success(f"Generation completed successfully in {duration:.3f}s.", stage="LLM")
                return result
            except Exception as e:
                logger.warning(f"[LLM] Fallback activation: Ollama failed with exception: {e}")
                console.warning(f"Ollama local connection failed ({e}). Activating OpenRouter cloud fallback...", stage="FALLBACK")
                res = await self._openrouter_generate(prompt)
                duration = time.monotonic() - t_start
                logger.info(f"[LLM] Inference duration (fallback exception): {duration:.3f}s")
                console.success(f"Fallback generation completed successfully in {duration:.3f}s.", stage="FALLBACK")
                return res

        if provider == "openrouter":
            res = await self._openrouter_generate(prompt)
            duration = time.monotonic() - t_start
            logger.info(f"[LLM] Inference duration: {duration:.3f}s")
            console.success(f"OpenRouter generation completed in {duration:.3f}s.", stage="LLM")
            return res

        if provider == "gemini":
            res = await self._gemini_generate(prompt)
            duration = time.monotonic() - t_start
            logger.info(f"[LLM] Inference duration: {duration:.3f}s")
            console.success(f"Gemini generation completed in {duration:.3f}s.", stage="LLM")
            return res

        # Unknown provider — try in order
        for fn in (self._ollama_generate, self._openrouter_generate):
            try:
                res = await fn(prompt, model) if fn == self._ollama_generate else await fn(prompt)
                if res and not res.startswith("[SYSTEM]"):
                    duration = time.monotonic() - t_start
                    logger.info(f"[LLM] Inference duration (auto-fallback): {duration:.3f}s")
                    console.success(f"Auto-fallback generation completed in {duration:.3f}s.", stage="LLM")
                    return res
            except Exception:
                continue

        console.error("All configured LLM providers failed to generate a response.", stage="LLM")
        return "I'm temporarily unable to generate a response. Please try again."

    async def generate_stream(
        self, prompt: str, model: str | None = None
    ) -> AsyncGenerator[str, None]:
        import time
        from backend.utils.console import console
        provider = self.settings.llm_provider.lower()
        t_start = time.monotonic()
        first_token_time = None

        logger.info(f"[WS] Streaming lifecycle: Starting stream using provider={provider}")
        console.info(f"LLM is working: starting live inference token streaming using {provider.upper()}...", stage="LLM")

        if provider == "ollama":
            try:
                async for token in self._ollama_stream(prompt, model):
                    if first_token_time is None:
                        first_token_time = time.monotonic()
                        latency = first_token_time - t_start
                        logger.info(f"[LLM] First token latency: {latency:.3f}s")
                        console.info(f"First token received in {latency:.3f}s.", stage="LLM")
                    
                    if token.startswith("[SYSTEM]") or token.startswith("[ERROR]"):
                        # Switch mid-stream to OpenRouter (streaming fallback)
                        logger.warning(f"[LLM] Fallback activation: Ollama failed mid-stream, switching to OpenRouter. msg={token}")
                        console.warning("Ollama streaming connection faulted mid-stream. Activating OpenRouter cloud fallback...", stage="FALLBACK")
                        async for fb_token in self._openrouter_stream(prompt):
                            if first_token_time is None:
                                first_token_time = time.monotonic()
                                logger.info(f"[LLM] First token latency (fallback): {first_token_time - t_start:.3f}s")
                            yield fb_token
                        duration = time.monotonic() - t_start
                        logger.info(f"[LLM] Inference duration (fallback): {duration:.3f}s")
                        logger.info(f"[WS] Streaming lifecycle: Fallback stream completed successfully in {duration:.3f}s")
                        console.success(f"Fallback streaming completed in {duration:.3f}s.", stage="FALLBACK")
                        return
                    
                    yield token
                
                duration = time.monotonic() - t_start
                logger.info(f"[LLM] Inference duration: {duration:.3f}s")
                logger.info(f"[WS] Streaming lifecycle: Stream completed successfully in {duration:.3f}s")
                console.success(f"Live token streaming completed successfully in {duration:.3f}s.", stage="LLM")
                return
            except Exception as e:
                logger.warning(f"[LLM] Fallback activation: Ollama failed with exception: {e}. Switching to OpenRouter.")
                console.warning(f"Ollama streaming connection failed ({e}). Activating OpenRouter cloud fallback...", stage="FALLBACK")
                async for fb_token in self._openrouter_stream(prompt):
                    yield fb_token
                duration = time.monotonic() - t_start
                logger.info(f"[LLM] Inference duration (fallback exception): {duration:.3f}s")
                logger.info(f"[WS] Streaming lifecycle: Fallback stream completed in {duration:.3f}s")
                console.success(f"Fallback streaming completed in {duration:.3f}s.", stage="FALLBACK")
                return

        if provider == "openrouter":
            async for token in self._openrouter_stream(prompt):
                if first_token_time is None:
                    first_token_time = time.monotonic()
                    logger.info(f"[LLM] First token latency: {first_token_time - t_start:.3f}s")
                    console.info(f"First token received in {first_token_time - t_start:.3f}s.", stage="LLM")
                yield token
            duration = time.monotonic() - t_start
            logger.info(f"[LLM] Inference duration: {duration:.3f}s")
            logger.info(f"[WS] Streaming lifecycle: OpenRouter stream completed in {duration:.3f}s")
            console.success(f"OpenRouter streaming completed in {duration:.3f}s.", stage="LLM")
            return

        if provider == "gemini":
            result = await self._gemini_generate(prompt)
            if first_token_time is None:
                first_token_time = time.monotonic()
                logger.info(f"[LLM] First token latency (Gemini): {first_token_time - t_start:.3f}s")
                console.info(f"Inference latency (Gemini): {first_token_time - t_start:.3f}s.", stage="LLM")
            for chunk in _chunk_string(result, 8):
                yield chunk
            duration = time.monotonic() - t_start
            logger.info(f"[LLM] Inference duration: {duration:.3f}s")
            logger.info(f"[WS] Streaming lifecycle: Gemini completed in {duration:.3f}s")
            console.success(f"Gemini streaming completed in {duration:.3f}s.", stage="LLM")
            return

        # Fallback
        console.error(f"Provider {provider.upper()} is not available. Emitting generic error message.", stage="LLM")
        yield "I'm temporarily unable to generate a response."

    # ------------------------------------------------------------------
    # Provider implementations
    # ------------------------------------------------------------------

    async def _ollama_generate(self, prompt: str, model: str | None = None) -> str:
        from backend.llm.ollama_client import ollama_client
        m = model or self.settings.ollama_model
        return await ollama_client.generate(prompt, model=m)

    async def _ollama_stream(
        self, prompt: str, model: str | None = None
    ) -> AsyncGenerator[str, None]:
        from backend.llm.ollama_client import ollama_client
        m = model or self.settings.ollama_model
        async for token in ollama_client.generate_stream(prompt, model=m):
            yield token

    async def _openrouter_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """Stream from OpenRouter /chat/completions using Server-Sent Events."""
        import httpx
        import json

        if not self.settings.openrouter_api_key:
            yield "[SYSTEM] OpenRouter API key not configured."
            return

        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://tio-platform.local",
            "X-Title": "TiO Intelligence Platform",
        }
        payload = {
            "model": self.settings.openrouter_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1024,
            "temperature": 0.4,
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.settings.openrouter_base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        line = line.strip()
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                choice = data.get("choices", [{}])[0]
                                delta = choice.get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            logger.error(f"[LLM][OpenRouter] Stream failed: {e}")
            yield f"[SYSTEM] OpenRouter stream failed: {e}"

    async def _openrouter_generate(self, prompt: str) -> str:
        """Call OpenRouter /chat/completions (non-streaming)."""
        import httpx

        if not self.settings.openrouter_api_key:
            return "[SYSTEM] OpenRouter API key not configured."

        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://tio-platform.local",
            "X-Title": "TiO Intelligence Platform",
        }
        payload = {
            "model": self.settings.openrouter_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1024,
            "temperature": 0.4,
        }

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(
                    f"{self.settings.openrouter_base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                logger.info(
                    f"[LLM][OpenRouter] model={self.settings.openrouter_model} "
                    f"tokens={data.get('usage', {}).get('total_tokens', '?')}"
                )
                return content
        except httpx.HTTPStatusError as e:
            logger.error(f"[LLM][OpenRouter] HTTP {e.response.status_code}: {e.response.text[:200]}")
            return f"[SYSTEM] OpenRouter error: {e.response.status_code}"
        except Exception as e:
            logger.error(f"[LLM][OpenRouter] Failed: {e}")
            return f"[SYSTEM] OpenRouter unavailable: {e}"

    async def _gemini_generate(self, prompt: str) -> str:
        """Call Gemini via google-generativeai SDK."""
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.settings.gemini_api_key)
            model = genai.GenerativeModel(self.settings.gemini_model)
            resp = await asyncio.to_thread(model.generate_content, prompt)
            return resp.text
        except Exception as e:
            logger.error(f"[LLM][Gemini] Failed: {e}")
            return f"[SYSTEM] Gemini unavailable: {e}"

    async def is_available(self) -> bool:
        """Quick health check — True if at least one provider can respond."""
        provider = self.settings.llm_provider.lower()
        if provider == "openrouter":
            return bool(self.settings.openrouter_api_key)
        if provider == "gemini":
            return bool(self.settings.gemini_api_key)
        # Ollama check
        from backend.llm.ollama_client import ollama_client
        return await ollama_client.is_available()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chunk_string(text: str, size: int):
    """Yield text in chunks of `size` characters for streaming simulation."""
    for i in range(0, len(text), size):
        yield text[i:i + size]


# Singleton
llm_router = LLMRouter()
