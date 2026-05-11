from backend.llm.ollama_client import ollama_client
from backend.llm.gemini_client import gemini_client
from backend.rag.types import RetrievedChunk
from backend.config.settings import get_settings

settings = get_settings()

def _build_prompt(query: str, contexts: list[RetrievedChunk], history: list[dict] = None, memory_context: str = "") -> str:
    data_block = "\n\n".join([f"Source [{i+1}]: {c.document}\n{c.text}" for i, c in enumerate(contexts)]) if contexts else "NO ASSETS."
    history_str = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in history[-3:]]) if history else ""
    
    return f"""You are TiO, a high-performance conversational intelligence. 

CORE DIRECTIVES:
- CONCISENESS: Be direct and efficient. Answer thoroughly but avoid unnecessary fluff.
- INTEGRATION: Seamlessly blend knowledge assets and memory.
- CITATIONS: Use [1], [2] format naturally within your text.

INTERNAL KNOWLEDGE ASSETS:
{data_block}

SESSION INTELLIGENCE:
{memory_context}

CHAT HISTORY:
{history_str}

USER: {query}
TiO (Direct & Fast):"""

async def iterative_refine(query: str, contexts: list[RetrievedChunk], history: list[dict] = None, memory_context: str = "") -> str:
    prompt = _build_prompt(query, contexts, history, memory_context=memory_context)
    if settings.llm_provider == "gemini":
        return await gemini_client.generate(prompt)
    return await ollama_client.generate(prompt, model=settings.ollama_model)

async def iterative_refine_stream(query: str, contexts: list[RetrievedChunk], history: list[dict] = None, memory_context: str = ""):
    prompt = _build_prompt(query, contexts, history, memory_context=memory_context)
    if settings.llm_provider == "gemini":
        async for chunk in gemini_client.generate_stream(prompt):
            yield chunk
    else:
        async for chunk in ollama_client.generate_stream(prompt, model=settings.ollama_model):
            yield chunk
