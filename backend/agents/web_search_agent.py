from duckduckgo_search import DDGS
from backend.rag.types import RetrievedChunk
import asyncio

async def search_web(query: str, limit: int = 8) -> list[RetrievedChunk]:
    """Perform a web search and return results as RetrievedChunks for RAG compatibility."""
    search_query = query
    if any(k in query.lower() for k in ["how to", "opinion", "best", "review", "minecraft", "bot"]):
        search_query += " reddit community discussion"

    try:
        # Wrap blocking DDGS call in a thread with a timeout
        def _fetch():
            with DDGS() as ddgs:
                return list(ddgs.text(search_query, max_results=limit))

        results = await asyncio.wait_for(asyncio.to_thread(_fetch), timeout=10.0)
            
        chunks = []
        for i, res in enumerate(results):
            is_community = any(c in res['href'].lower() for c in ["reddit.com", "stackexchange", "github", "forum"])
            score = (1.0 - (i * 0.05)) + (0.2 if is_community else 0.0)
            
            chunks.append(RetrievedChunk(
                chunk_id=f"web-{i}",
                text=f"{res['title']}: {res['body']}",
                document=res['href'],
                score=min(1.0, score),
                metadata={"url": res['href'], "source": "web", "is_community": is_community}
            ))
        return sorted(chunks, key=lambda x: x.score, reverse=True)
    except asyncio.TimeoutError:
        print(f"Web search timed out for query: {query}")
        return []
    except Exception as e:
        print(f"Web search error: {e}")
        return []
