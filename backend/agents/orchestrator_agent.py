from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.llm.ollama_client import ollama_client
from backend.config.settings import get_settings
from backend.vectorstore.service import async_retrieve
from backend.llm.profiles import get_profile
from backend.models.entities import Conversation, Chatbot
from backend.rag.safety import sanitize_input, sanitize_output
import asyncio

settings = get_settings()

async def _get_context(query: str, chatbot_id: int):
    chunks = await async_retrieve(query, top_k=settings.top_k, chatbot_id=chatbot_id)
    context_str = "\n".join([f"Source [{i+1}]: {c.text}" for i, c in enumerate(chunks)])
    return chunks, context_str

async def _get_chatbot_details(db: AsyncSession, chatbot_id: int | None = None, session_id: str | None = None):
    if not chatbot_id and session_id:
        stmt = select(Conversation).where(Conversation.session_id == session_id)
        conv = (await db.execute(stmt)).scalar_one_or_none()
        if conv:
            chatbot_id = conv.chatbot_id
    
    if chatbot_id:
        chatbot = await db.get(Chatbot, chatbot_id)
        return chatbot
    return None

async def run_orchestration(
    query: str, 
    history: list[dict], 
    db: AsyncSession, 
    chatbot_id: int | None = None,
    session_id: str | None = None,
    domain: str | None = None,
    profile: str | None = None
) -> dict:
    query = sanitize_input(query)
    chatbot = await _get_chatbot_details(db, chatbot_id, session_id)
    effective_chatbot_id = chatbot.id if chatbot else None
    
    # 1. Get Behavior Profile
    bp = get_profile(profile or (chatbot.behavior_profile if chatbot else None) or (chatbot.domain if chatbot else None))
    
    # 2. Hybrid Retrieval
    chunks, context_str = await _get_context(query, effective_chatbot_id)
    
    # 3. Assemble Prompt
    system_prompt = f"""{bp.instructions}

CONTEXT FROM WEBSITE AND DOCUMENTS:
{context_str if chunks else "No specific documents found. Answer based on general knowledge within the business context."}

TONE: {bp.tone}
"""
    
    messages = [{"role": "system", "content": system_prompt}]
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": query})
    
    prompt = ""
    for m in messages:
        prompt += f"{m['role'].upper()}: {m['content']}\n"
    prompt += "ASSISTANT: "
    
    answer = await ollama_client.generate(prompt, model=settings.ollama_model)
    answer = sanitize_output(answer)
    
    return {
        "answer": answer,
        "citations": [c.__dict__ for c in chunks],
        "suggestions": bp.suggestions if not history else [],
        "domain": chatbot.domain if chatbot else None,
        "profile": bp.name
    }

async def run_orchestration_stream(
    query: str, 
    history: list[dict], 
    db: AsyncSession, 
    chatbot_id: int | None = None,
    session_id: str | None = None
):
    query = sanitize_input(query)
    chatbot = await _get_chatbot_details(db, chatbot_id, session_id)
    effective_chatbot_id = chatbot.id if chatbot else None
    
    # 1. Get Profile
    profile_name = (chatbot.behavior_profile if chatbot else None) or (chatbot.domain if chatbot else None)
    bp = get_profile(profile_name)
    
    # 2. Retrieve Context
    chunks, context_str = await _get_context(query, effective_chatbot_id)
    
    # Emit metadata first
    yield {
        "type": "metadata",
        "citations": [c.__dict__ for c in chunks],
        "intent": "grounded" if chunks else "conversational"
    }
    
    # 3. Assemble Prompt
    system_prompt = f"""{bp.instructions}

CONTEXT FROM WEBSITE AND DOCUMENTS:
{context_str if chunks else "No specific documents found."}

TONE: {bp.tone}
"""
    
    messages = [{"role": "system", "content": system_prompt}]
    for h in history:
        # History objects might have 'role' and 'content'
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": query})
    
    prompt = ""
    for m in messages:
        prompt += f"{m['role'].upper()}: {m['content']}\n"
    prompt += "ASSISTANT: "
    
    # 4. Stream
    async for chunk in ollama_client.generate_stream(prompt, model=settings.ollama_model):
        yield {
            "type": "token",
            "content": chunk
        }
