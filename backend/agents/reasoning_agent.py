from backend.rag.iterative_refinement import iterative_refine, iterative_refine_stream


async def reason(query: str, chunks: list, history: list[dict] = None, memory_context: str = ""):
    return await iterative_refine(query, chunks, history, memory_context=memory_context)

async def reason_stream(query: str, chunks: list, history: list[dict] = None, memory_context: str = ""):
    async for chunk in iterative_refine_stream(query, chunks, history, memory_context=memory_context):
        yield chunk
