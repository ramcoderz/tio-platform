import httpx
import json
import asyncio
import time
import logging

logger = logging.getLogger(__name__)
from backend.config.settings import get_settings

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
            
    async def _openrouter_generate_stream(self, prompt: str):
        if not self.settings.openrouter_api_key:
            yield "ERROR: Ollama server is offline and no OpenRouter API key is configured for fallback."
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
            "stream": True
        }
        
        try:
            async with self.client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            data = json.loads(line[6:])
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                if "content" in delta:
                                    yield delta["content"]
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            yield f"\n[OpenRouter Fallback Error: {e}]"

    async def _openrouter_generate(self, prompt: str) -> str:
        if not self.settings.openrouter_api_key:
            return "ERROR: Ollama server is offline and no OpenRouter API key is configured for fallback."
            
        url = f"{self.settings.openrouter_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.settings.openrouter_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        }
        
        try:
            res = await self.client.post(url, headers=headers, json=payload)
            res.raise_for_status()
            return res.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"[OpenRouter Fallback Error: {e}]"

    async def generate_stream(self, prompt: str, model: str = "llama3"):
        if not await self.is_available() or not await self.has_model(model):
            async for chunk in self._openrouter_generate_stream(prompt):
                yield chunk
            return

        url = f"{self.base_url}/api/generate"
        payload = {"model": model, "prompt": prompt, "stream": True}
        logger.debug(f"Ollama generate_stream URL: {url}, Model: {model}")

        try:
            async with self.client.stream("POST", url, json=payload) as response:
                logger.debug(f"Ollama response status: {response.status_code}")
                if response.status_code == 404:
                    yield f"ERROR: Model '{model}' not found in Ollama. Please run 'ollama pull {model}'."
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
            # Try fallback on failure during streaming? It's messy mid-stream. 
            # We will just yield the error.
            yield f"\n[Ollama Generation Error: {e}]"

    async def generate(self, prompt: str, model: str = "llama3") -> str:
        if not await self.is_available() or not await self.has_model(model):
            return await self._openrouter_generate(prompt)

        url = f"{self.base_url}/api/generate"
        payload = {"model": model, "prompt": prompt, "stream": False}
        
        try:
            res = await self.client.post(url, json=payload)
            res.raise_for_status()
            return res.json().get("response", "")
        except Exception as e:
            # Fallback if request fails
            return await self._openrouter_generate(prompt)

ollama_client = OllamaClient()
