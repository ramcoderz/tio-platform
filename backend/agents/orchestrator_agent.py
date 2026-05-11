from sqlalchemy.ext.asyncio import AsyncSession
from backend.agents.query_refinement_agent import refine_query
from backend.agents.reasoning_agent import reason, reason_stream
from backend.agents.retrieval_agent import retrieve_chunks, retrieve_chunks_for_session
from backend.agents.web_search_agent import search_web
from backend.agents.validation_agent import validate
from backend.llm.ollama_client import ollama_client
from backend.llm.gemini_client import gemini_client
from backend.config.settings import get_settings
import time
import asyncio
import numpy as np
from backend.rag.embeddings import embed

from backend.agents.specialized_agents import compare_documents, extract_structured_data, orchestrate_tasks
from backend.utils.audit import log_activity
from backend.utils.cache import semantic_cache
from backend.rag.iterative_refinement import _build_prompt

settings = get_settings()
# Cache logic handled by semantic_cache utility
async def clear_session_response_cache(session_id: str):
    await semantic_cache.clear_session(session_id)

# Lightweight conversational intent heuristic
def is_conversational(query: str) -> bool:
    q = query.lower().strip()
    conversational_phrases = [
        "hello", "hi", "how are you", "who are you", "thanks", "thank you", 
        "goodbye", "bye", "hey", "good morning", "good afternoon"
    ]
    if q in conversational_phrases or (len(q.split()) < 3 and "?" not in q and "this" not in q):
        return True
    return False

def is_overview_query(query: str) -> bool:
    q = query.lower().strip()
    overview_keywords = [
        "about", "summary", "summarize", "overview", "what is this", "tell me about",
        "image", "picture", "photo", "pdf", "document"
    ]
    # If the query is short and contains overview keywords, it's likely an overview request
    return any(k in q for k in overview_keywords) and len(q.split()) < 10



from sqlalchemy.ext.asyncio import AsyncSession

async def extract_and_store_entities(text: str, session_id: str, db: AsyncSession):
    # Very fast regex-based extraction for common entities (Project names, etc)
    # In a full prod app, we might use a small LLM call for this in background
    import re
    from backend.models.entities import SessionMemory
    
    # Try to find "Project: X" or "I am working on X"
    match = re.search(r"(?:project|working on)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", text)
    if match:
        name = match.group(1).strip()
        db.add(SessionMemory(session_id=session_id, key="current_project", value=name))
        await db.commit()

async def get_session_entities(session_id: str, db: AsyncSession) -> str:
    from backend.models.entities import SessionMemory
    from sqlalchemy import select
    rows = (await db.execute(select(SessionMemory).where(SessionMemory.session_id == session_id))).scalars().all()
    if not rows: return ""
    return "\n".join([f"Entity: {r.key} = {r.value}" for r in rows])

# --- Tiered Query Routing ---
def classify_query(query: str) -> str:
    """Lightweight intent classification using regex and heuristics."""
    q = query.lower().strip()
    
    # 1. Image/OCR Query
    if any(k in q for k in ["image", "picture", "photo", "screenshot", "extract text from"]):
        return "ocr"
    
    # 2. Conversational Query
    conversational_phrases = ["hello", "hi", "how are you", "who are you", "thanks", "thank you", "bye"]
    if q in conversational_phrases or (len(q.split()) < 3 and "?" not in q):
        return "conversational"
    
    # 3. Document Query (Explicit mention of docs)
    doc_keywords = ["document", "pdf", "report", "file", "summarize the", "what does the doc", "compare these"]
    if any(k in q for k in doc_keywords):
        return "document"
        
    # 4. Research/Complex Query
    research_keywords = ["analyze", "compare", "tradeoffs", "architectural", "bottlenecks", "explain in detail", "deep dive"]
    if any(k in q for k in research_keywords) or len(q.split()) > 15:
        return "research"
        
    # Default: Simple Knowledge Query
    return "simple"

async def run_orchestration(query: str, history: list[dict], db: AsyncSession, session_id: str | None = None) -> dict:
    # 0. Initialize response state
    full_answer = ""
    citations = []
    confidence = 1.0
    needs_clarification = False
    
    # 1. Semantic Cache Check (Instant fallback)
    q_vec = np.array(embed([query])[0], dtype="float32")
    cached = await semantic_cache.get_semantic(q_vec)
    if cached: return cached

    # 2. Intent Routing
    intent = classify_query(query)
    
    # 3. Execution Paths
    if intent in ["simple", "conversational"]:
        # Direct LLM Path - Skip RAG
        prompt = f"""CORE DIRECTIVES:
- DEPTH: Provide thorough and detailed explanations. Aim for a substantial and informative response while maintaining focus and high word count.
- ADAPTIVE TONE: Adjust your tone to the user. If they are technical, be precise. If casual, be conversational.
- NATURAL FLOW: Avoid robotic structure. Use bullet points ONLY when listing distinct items. Prefer cohesive, intelligent paragraphs for explanations.
- DIRECTNESS: Answer immediately. No meta-talk about "searching" or "context."
- INTEGRATION: Seamlessly blend knowledge assets and memory into your response.
- CITATIONS: You MUST refer to sources using [1], [2] format naturally within your text.

You are TiO. Answer this with a thorough and informative explanation: {query}"""
        if intent == "conversational":
            prompt = f"""CORE DIRECTIVES:
- DEPTH: Provide thorough and detailed explanations. Aim for a substantial and informative response while maintaining focus and high word count.
- ADAPTIVE TONE: Adjust your tone to the user. If they are technical, be precise. If casual, be conversational.
- NATURAL FLOW: Avoid robotic structure. Use bullet points ONLY when listing distinct items. Prefer cohesive, intelligent paragraphs for explanations.
- DIRECTNESS: Answer immediately. No meta-talk about "searching" or "context."
- INTEGRATION: Seamlessly blend knowledge assets and memory into your response.
- CITATIONS: You MUST refer to sources using [1], [2] format naturally within your text.

You are TiO, a helpful AI assistant. Chat naturally and provide detailed insights where appropriate: {query}"""
        
        full_answer = await ollama_client.generate(prompt, model=settings.ollama_model)
        result = {
            "answer": full_answer,
            "confidence": 1.0,
            "citations": [],
            "needs_clarification": False,
            "intent": intent
        }
        await semantic_cache.set_semantic(q_vec, result, session_id)
        return result

    # --- RAG Paths (Document/Research/OCR) ---
    # Query Refinement (Optional for RAG)
    refined = query
    if len(query.split()) > 8:
        refinement_prompt = f"Rewrite this query for optimal RAG retrieval. \nQuery: {query}"
        refined = await ollama_client.generate(refinement_prompt, model=settings.ollama_model)

    # Parallel Retrieval Execution
    from backend.vectorstore.service import async_retrieve
    k = settings.top_k if intent == "document" else settings.top_k + 2
    chunks = await async_retrieve(refined, k, session_id=session_id)
    
    if not chunks and intent == "research":
        chunks = await search_web(refined)

    # Specialized Reasoning
    if intent == "research":
        mem_context = await get_session_entities(session_id, db) if session_id else ""
        full_answer = await reason(refined, chunks, history, memory_context=mem_context)
    else:
        full_answer = await reason(refined, chunks, history)

    # Lightweight Validation
    confidence, needs_clarification = await validate(full_answer, chunks) if chunks else (1.0, False)
    
    result = {
        "answer": full_answer,
        "confidence": confidence,
        "citations": [c.__dict__ for c in chunks] if chunks else [],
        "needs_clarification": needs_clarification,
        "intent": intent
    }
    
    # Async background tasks for memory and activity logging
    if session_id:
        asyncio.create_task(extract_and_store_entities(query + " " + full_answer, session_id, db))
    asyncio.create_task(log_activity(db, None, "query_execution", resource=session_id, details=f"Intent: {intent}"))
    
    await semantic_cache.set_semantic(q_vec, result, session_id)
    return result

async def run_orchestration_stream(query: str, history: list[dict], db: AsyncSession, session_id: str | None = None):
    # 0. Initialize response state
    full_answer = ""
    q_vec = np.array(embed([query])[0], dtype="float32")
    
    # 1. Semantic Cache (Instant response)
    cached = await semantic_cache.get_semantic(q_vec)
    if cached:
        yield {"type": "metadata", "citations": cached["citations"]}
        for word in cached["answer"].split(" "):
            yield {"type": "token", "content": word + " "}
            await asyncio.sleep(0.01)
        return

    # 2. Intent Routing
    intent = classify_query(query)
    
    # 3. Simple/Conversational Paths
    if intent in ["simple", "conversational"]:
        yield {"type": "metadata", "citations": [], "intent": intent}
        prompt = f"You are TiO. Provide a detailed and helpful response: {query}"
        if intent == "conversational":
            prompt = f"You are TiO. Chat naturally and thoroughly: {query}"
            
        async for chunk in ollama_client.generate_stream(prompt, model=settings.ollama_model):
            full_answer += chunk
            yield {"type": "token", "content": chunk}
            
        # Background: Save to cache
        asyncio.create_task(semantic_cache.set_semantic(q_vec, {"answer": full_answer, "citations": []}, session_id))
        return

    # --- RAG Paths ---
    yield {"type": "thinking", "content": f"Identified {intent} intent. Initializing retrieval..."}
    
    # Parallel Retrieval & Context Prep
    from backend.vectorstore.service import async_retrieve
    
    # Only refine if query is complex
    if len(query.split()) > 6:
        refined_task = asyncio.create_task(refine_query(query, history))
    else:
        refined_task = None

    k = settings.top_k if intent == "document" else settings.top_k + 2
    
    # Start retrieval immediately using original query (faster)
    chunks_task = asyncio.create_task(async_retrieve(query, k, session_id=session_id))
    
    # While retrieving, show progress
    yield {"type": "thinking", "content": "Searching workspace intelligence..."}
    chunks = await chunks_task
    
    # If refined query is ready and retrieval was empty, try again with refined (fallback)
    if not chunks and refined_task:
        refined = await refined_task
        chunks = await async_retrieve(refined, k, session_id=session_id)
    elif refined_task:
        # Await it anyway to clean up, but use chunks from original
        await refined_task
    
    # 4. Immediate Metadata Stream
    refined_query = query
    if not chunks and intent == "research":
        yield {"type": "thinking", "content": "Local knowledge base exhausted. Performing web research..."}
        if refined_task:
            refined_query = await refined_task
        chunks = await search_web(refined_query)

    yield {"type": "metadata", "citations": [c.__dict__ for c in chunks], "intent": intent}
    yield {"type": "thinking", "content": "Synthesizing research brief..."}

    # 5. Reasoning & Streaming tokens
    mem_context = await get_session_entities(session_id, db) if session_id else ""
    try:
        async for chunk in reason_stream(refined, chunks, history, memory_context=mem_context):
            full_answer += chunk
            yield {"type": "token", "content": chunk}
    except Exception as e:
        yield {"type": "token", "content": f"\n[Switching to secondary intelligence...] "}
        async for o_chunk in ollama_client.generate_stream(_build_prompt(refined, chunks, history, memory_context=mem_context), model=settings.ollama_model):
            full_answer += o_chunk
            yield {"type": "token", "content": o_chunk}

    # 6. Async Post-Processing (Background)
    if session_id:
        asyncio.create_task(extract_and_store_entities(query + " " + full_answer, session_id, db))
    
    confidence, _ = await validate(full_answer, chunks) if chunks else (1.0, False)
    asyncio.create_task(semantic_cache.set_semantic(q_vec, {
        "answer": full_answer,
        "confidence": confidence,
        "citations": [c.__dict__ for c in chunks] if chunks else [],
        "needs_clarification": False
    }, session_id))

