import asyncio
from backend.config.settings import get_settings
from backend.vectorstore.service import retrieve

settings = get_settings()


async def retrieve_chunks(refined_query: str, top_k: int | None = None):
    return await asyncio.to_thread(retrieve, refined_query, top_k or settings.top_k, None)


async def retrieve_chunks_for_session(refined_query: str, session_id: str, top_k: int | None = None):
    return await asyncio.to_thread(retrieve, refined_query, top_k or settings.top_k, session_id)
