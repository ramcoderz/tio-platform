import json
import pickle
import time
from typing import Any, Optional
import numpy as np
import redis.asyncio as redis
from backend.config.settings import get_settings

settings = get_settings()

class HybridCache:
    """
    A robust caching layer that uses Redis if available, 
    falling back to an in-memory dictionary for development.
    Supports Semantic Caching, Key-Value Caching, and Activity Feeds.
    """
    def __init__(self):
        self.redis_enabled = False
        self.redis = None
        self._memory_cache = {} # fallback: key -> (expire_at, data)
        self._memory_semantic = [] # fallback: list of {vec, result, session_id, expire_at}
        self.threshold = 0.95
        self.ttl = 3600

        # Attempt to connect to Redis
        try:
            self.redis = redis.from_url(settings.redis_url, socket_timeout=1)
            self.redis_enabled = True
            print("INFO: Local Redis detected. Semantic cache enabled.")
        except Exception:
            print("WARNING: Local Redis not found. Falling back to in-memory cache.")
            self.redis_enabled = False

    async def _is_redis_alive(self) -> bool:
        if not self.redis_enabled or not self.redis:
            return False
        try:
            await self.redis.ping()
            return True
        except Exception:
            self.redis_enabled = False
            return False

    # --- Semantic Caching ---
    async def get_semantic(self, query_vec: np.ndarray) -> Optional[dict]:
        if await self._is_redis_alive():
            try:
                keys = await self.redis.keys("semcache:*")
                for key in keys:
                    data_raw = await self.redis.get(key)
                    if not data_raw: continue
                    item = pickle.loads(data_raw)
                    sim = np.dot(query_vec, item["vec"]) / (np.linalg.norm(query_vec) * np.linalg.norm(item["vec"]))
                    if sim > self.threshold:
                        res = item["result"]
                        res["cache_hit"] = "redis"
                        res["similarity"] = float(sim)
                        return res
            except Exception as e:
                print(f"Redis Semantic Error: {e}")

        # Fallback to in-memory
        now = time.time()
        for item in self._memory_semantic:
            if item["expire_at"] < now: continue
            sim = np.dot(query_vec, item["vec"]) / (np.linalg.norm(query_vec) * np.linalg.norm(item["vec"]))
            if sim > self.threshold:
                res = dict(item["result"])
                res["cache_hit"] = "memory"
                res["similarity"] = float(sim)
                return res
        return None

    async def set_semantic(self, query_vec: np.ndarray, result: dict, session_id: Optional[str] = None):
        expire_at = time.time() + self.ttl
        if await self._is_redis_alive():
            try:
                import uuid
                key = f"semcache:{uuid.uuid4()}"
                data = {"vec": query_vec, "result": result, "session_id": session_id}
                await self.redis.setex(key, self.ttl, pickle.dumps(data))
                return
            except Exception as e:
                print(f"Redis Set Semantic Error: {e}")

        # In-memory fallback
        self._memory_semantic.append({
            "vec": query_vec, 
            "result": result, 
            "session_id": session_id,
            "expire_at": expire_at
        })
        # Basic cleanup: keep last 1000
        if len(self._memory_semantic) > 1000:
            self._memory_semantic = self._memory_semantic[-1000:]

    # --- Key-Value Caching (State/Feeds) ---
    async def get(self, key: str) -> Any:
        if await self._is_redis_alive():
            try:
                val = await self.redis.get(key)
                return json.loads(val) if val else None
            except Exception: pass
        
        # Memory
        entry = self._memory_cache.get(key)
        if entry and entry[0] > time.time():
            return entry[1]
        return None

    async def set(self, key: str, value: Any, ttl: int = 3600):
        if await self._is_redis_alive():
            try:
                await self.redis.setex(key, ttl, json.dumps(value))
                return
            except Exception: pass
        
        self._memory_cache[key] = (time.time() + ttl, value)

    # --- Activity Feed (Lists) ---
    async def push_activity(self, activity: dict):
        if await self._is_redis_alive():
            try:
                await self.redis.lpush("activity_feed", json.dumps(activity))
                await self.redis.ltrim("activity_feed", 0, 99) # Keep last 100
                return
            except Exception: pass
        
        # Memory fallback
        feed = self._memory_cache.get("activity_feed", (float('inf'), []))[1]
        feed.insert(0, activity)
        self._memory_cache["activity_feed"] = (float('inf'), feed[:100])

    async def get_activity_feed(self) -> list:
        if await self._is_redis_alive():
            try:
                items = await self.redis.lrange("activity_feed", 0, 49)
                return [json.loads(i) for i in items]
            except Exception: pass
        return self._memory_cache.get("activity_feed", (0, []))[1]

    async def clear_session(self, session_id: str):
        if await self._is_redis_alive():
            try:
                keys = await self.redis.keys("semcache:*")
                for k in keys:
                    raw = await self.redis.get(k)
                    if raw and pickle.loads(raw).get("session_id") == session_id:
                        await self.redis.delete(k)
            except Exception: pass
        
        self._memory_semantic = [i for i in self._memory_semantic if i.get("session_id") != session_id]

# Single instance
semantic_cache = HybridCache()
