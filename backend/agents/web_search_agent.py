from duckduckgo_search import DDGS
from backend.rag.types import RetrievedChunk

async def search_web(query: str, limit: int = 8) -> list[RetrievedChunk]:
    """Perform a web search and return results as RetrievedChunks for RAG compatibility."""
    # Enrich query for community insights if it's niche
    search_query = query
    if any(k in query.lower() for k in ["how to", "opinion", "best", "review", "minecraft", "bot"]):
        search_query += " reddit community discussion"

    try:
        with DDGS() as ddgs:
            # Increase max_results to allow for filtering
            results = list(ddgs.text(search_query, max_results=limit))
            
        chunks = []
        for i, res in enumerate(results):
            # Prioritize Reddit/Community results in scoring
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
    except Exception as e:
        print(f"Web search error: {e}")
        return []
