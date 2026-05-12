"""
Orchestration: Query → Intent Detection → Hybrid Retrieval → Response

Flow is intentionally simple:
  1. Sanitize input
  2. Classify intent (lightweight keyword + embedding match)
  3. Retrieve relevant chunks (hybrid BM25 + vector + RRF)
  4. Assemble prompt with domain behavior profile
  5. Stream or generate response
  6. Sanitize output
"""

import asyncio
import time
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.llm.ollama_client import ollama_client
from backend.config.settings import get_settings
from backend.vectorstore.service import async_retrieve
from backend.llm.profiles import get_profile
from backend.llm.skills import get_skill_guidance
from backend.models.entities import Conversation, Chatbot
from backend.rag.safety import sanitize_input, sanitize_output
from backend.utils.monitoring import track_query
from backend.utils.domain_intelligence import domain_detector
from backend.utils.intent_intelligence import intent_intelligence

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# INTENT DETECTION — lightweight keyword routing
# ---------------------------------------------------------------------------

INTENT_PATTERNS: dict[str, list[str]] = {
    # Tourism
    "tourism_planner": ["plan", "itinerary", "trip", "travel", "visit", "schedule", "route", "weekend"],
    "attraction_recommender": ["attractions", "things to do", "places to see", "must see", "popular"],
    "ride_optimizer": ["wait time", "queue", "rides", "skip the line", "fast pass"],
    
    # Education
    "course_finder": ["course", "program", "major", "degree", "study", "curriculum", "syllabus"],
    "admission_assistant": ["admission", "apply", "enroll", "deadline", "requirements", "eligibility"],
    "scholarship_helper": ["scholarship", "financial aid", "grant", "funding", "bursary"],
    
    # Medical
    "dept_navigator": ["department", "specialist", "pain", "symptom", "doctor", "consult", "hospital"],
    "appointment_guidance": ["appointment", "book", "schedule", "visiting hours", "contact"],
    "insurance_assistant": ["insurance", "coverage", "billing", "payment", "claims"],
    
    # Developer
    "api_assistant": ["api", "sdk", "code", "endpoint", "authenticate", "bearer", "token"],
    "integration_helper": ["integrate", "integration", "webhook", "event", "flow", "setup"],
    "sdk_guide": ["install", "library", "npm", "pip", "package", "init"],
    
    # Ecommerce
    "shopping_guide": ["product", "buy", "price", "pricing", "catalog", "compare", "best"],
    
    # General
    "doc_summarizer": ["summarize", "summary", "overview", "what is this", "tell me about", "highlights"],
}

# Domain → which skills are eligible
DOMAIN_SKILL_MAP: dict[str, list[str]] = {
    "tourism":   ["tourism_planner", "attraction_recommender", "ride_optimizer", "doc_summarizer"],
    "education": ["course_finder", "admission_assistant", "scholarship_helper", "doc_summarizer"],
    "medical":   ["dept_navigator", "appointment_guidance", "insurance_assistant", "doc_summarizer"],
    "developer": ["api_assistant", "integration_helper", "sdk_guide", "doc_summarizer"],
    "ecommerce": ["shopping_guide", "doc_summarizer"],
    "general":   ["doc_summarizer"],
}


def detect_intent(query: str, domain: str | None) -> str:
    """
    Hybrid intent detection: Keyword patterns + Semantic similarity.
    Returns the most likely skill name, or 'general_chat' if no pattern matches.
    """
    q = query.lower()
    # If domain is unknown, consider all skills
    eligible = DOMAIN_SKILL_MAP.get(domain, list(INTENT_PATTERNS.keys())) if domain != "general" else list(INTENT_PATTERNS.keys())

    # 1. Keyword check
    scores: dict[str, int] = {skill: 0 for skill in eligible}
    for skill in eligible:
        for kw in INTENT_PATTERNS.get(skill, []):
            if kw in q:
                scores[skill] += 1

    best_keyword_skill = max(scores, key=scores.get, default="general_chat")
    if scores.get(best_keyword_skill, 0) > 0:
        return best_keyword_skill
        
    # 2. Semantic fallback
    return intent_intelligence.detect(query, eligible_skills=eligible)


# ---------------------------------------------------------------------------
# CONTEXT RETRIEVAL
# ---------------------------------------------------------------------------

async def _get_context(
    query: str, chatbot_id: int | None
) -> tuple[list, str, float]:
    """Run hybrid retrieval, return (chunks, context_str, retrieval_ms)."""
    t0 = time.monotonic()
    chunks = await async_retrieve(query, top_k=settings.top_k, chatbot_id=chatbot_id)
    elapsed = (time.monotonic() - t0) * 1000

    if not chunks:
        logger.warning(f"[RETRIEVAL] No chunks found for query: {query!r} (chatbot={chatbot_id})")
        return [], "", elapsed

    context_str = "\n\n".join(
        f"[Source {i+1}: {c.document}]\n{c.text}"
        for i, c in enumerate(chunks)
    )
    return chunks, context_str, elapsed


# ---------------------------------------------------------------------------
# CHATBOT LOOKUP
# ---------------------------------------------------------------------------

async def _get_chatbot(
    db: AsyncSession,
    chatbot_id: int | None = None,
    session_id: str | None = None,
) -> "Chatbot | None":
    if chatbot_id:
        return await db.get(Chatbot, chatbot_id)

    if session_id:
        stmt = select(Conversation).where(Conversation.session_id == session_id)
        conv = (await db.execute(stmt)).scalar_one_or_none()
        if conv and conv.chatbot_id:
            return await db.get(Chatbot, conv.chatbot_id)

    return None


# ---------------------------------------------------------------------------
# PROMPT ASSEMBLY
# ---------------------------------------------------------------------------

def _build_prompt(
    query: str,
    history: list[dict],
    context_str: str,
    bp,
    intent: str,
) -> str:
    no_context_note = (
        "No specific content was retrieved from the knowledge base for this query. "
        "Provide the most helpful answer you can from your domain knowledge without fabricating specific facts."
    )

    skill_guidance = get_skill_guidance(intent)

    system = (
        f"{bp.instructions}\n\n"
        f"TONE: {bp.tone}\n\n"
        f"SKILL GUIDANCE: {skill_guidance}\n\n"
        f"RETRIEVED CONTEXT:\n{context_str if context_str else no_context_note}\n\n"
        f"DETECTED INTENT: {intent.replace('_', ' ')}"
    )

    parts = [f"SYSTEM: {system}"]
    for h in history[-8:]:  # cap history at last 8 turns to avoid token bloat
        role = h.get("role", "user").upper()
        parts.append(f"{role}: {h['content']}")
    
    # Add high-priority constraints at the very end (recency bias)
    constraints = (
        "CRITICAL CONSTRAINTS (DO NOT IGNORE):\n"
        "- NEVER use placeholders or bracketed tags like [Place], [Institution], or [Details].\n"
        "- If specific names or data are not in the RETRIEVED CONTEXT, admit it clearly.\n"
        "- Do NOT use generic templates for tourist attractions if names are missing."
    )
    parts.append(f"INSTRUCTION: {constraints}")
    
    parts.append(f"USER: {query}")
    parts.append("ASSISTANT:")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# PUBLIC API — Non-streaming (HTTP /chat fallback)
# ---------------------------------------------------------------------------

async def run_orchestration(
    query: str,
    history: list[dict],
    db: AsyncSession,
    chatbot_id: int | None = None,
    session_id: str | None = None,
    domain: str | None = None,
    profile: str | None = None,
) -> dict:
    query = sanitize_input(query)
    
    # 1. Normalize query for better retrieval
    normalized_query = intent_intelligence.normalize_query(query)
    if normalized_query != query.lower():
        logger.info(f"[ORCHESTRATOR] Normalized query: {query} -> {normalized_query}")
    
    chatbot = await _get_chatbot(db, chatbot_id, session_id)
    effective_id = chatbot.id if chatbot else None
    
    # Domain Intelligence fallback
    chatbot_domain = chatbot.domain if chatbot else None
    if not chatbot_domain or chatbot_domain == "general":
        # Check if we can detect it from context or query
        detected = domain_detector.detect(query, {"url": chatbot.website_url if chatbot else ""})
        effective_domain = detected if detected != "general" else "general"
    else:
        effective_domain = chatbot_domain

    effective_domain = domain or effective_domain

    # Intent
    intent = detect_intent(query, effective_domain)

    # Retrieval (use normalized query for better grounding)
    chunks, context_str, retrieval_ms = await _get_context(normalized_query, effective_id)

    # Profile
    bp = get_profile(profile or effective_domain)

    # Prompt
    prompt = _build_prompt(query, history, context_str, bp, intent)

    # Generate
    t0 = time.monotonic()
    answer = await ollama_client.generate(prompt, model=settings.ollama_model)
    
    # Post-generation validation: Check for bracketed placeholders
    if "[" in answer and "]" in answer:
        logger.warning(f"[ORCHESTRATOR] Placeholder detected in answer. Stripping brackets...")
        # Simple fix: remove brackets and content inside if it looks like a placeholder
        answer = re.sub(r'\[[A-Z][^\]]+\]', 'relevant areas', answer)
        # If it still has brackets, try one more generation with a stricter prompt or just return a safe fallback
        if "[" in answer and "]" in answer:
            answer = "I'm sorry, I couldn't identify specific entities for that request in the indexed context. The destination offers various attractions and services related to its domain."
            
    llm_ms = (time.monotonic() - t0) * 1000
    answer = sanitize_output(answer)

    # Log
    await track_query(
        query=query,
        intent=intent,
        domain=effective_domain,
        retrieved_chunks=len(chunks),
        retrieval_ms=retrieval_ms,
        llm_ms=llm_ms,
        answered=bool(chunks),
        citations=len(chunks),
    )

    return {
        "answer": answer,
        "citations": [c.__dict__ for c in chunks],
        "intent": intent,
        "suggestions": bp.suggestions if not history else [],
        "domain": effective_domain,
        "profile": bp.name,
    }


# ---------------------------------------------------------------------------
# PUBLIC API — Streaming (WebSocket /ws/chat)
# ---------------------------------------------------------------------------

async def run_orchestration_stream(
    query: str,
    history: list[dict],
    db: AsyncSession,
    chatbot_id: int | None = None,
    session_id: str | None = None,
):
    query = sanitize_input(query)
    
    # Normalize query for better retrieval
    normalized_query = intent_intelligence.normalize_query(query)
    
    chatbot = await _get_chatbot(db, chatbot_id, session_id)
    effective_id = chatbot.id if chatbot else None
    
    # Domain Intelligence fallback
    chatbot_domain = chatbot.domain if chatbot else None
    if not chatbot_domain or chatbot_domain == "general":
        detected = domain_detector.detect(query, {"url": chatbot.website_url if chatbot else ""})
        effective_domain = detected if detected != "general" else "general"
    else:
        effective_domain = chatbot_domain

    # Intent
    intent = detect_intent(query, effective_domain)

    # Retrieval (use normalized query for better grounding)
    chunks, context_str, retrieval_ms = await _get_context(normalized_query, effective_id)

    # Emit metadata before streaming starts
    yield {
        "type": "metadata",
        "citations": [c.__dict__ for c in chunks],
        "intent": intent,
        "domain": effective_domain,
    }

    # Profile + Prompt
    bp = get_profile(effective_domain)
    prompt = _build_prompt(query, history, context_str, bp, intent)

    # Stream
    t0 = time.monotonic()
    full_answer = ""
    async for token in ollama_client.generate_stream(prompt, model=settings.ollama_model):
        full_answer += token
        yield {"type": "token", "content": token}

    llm_ms = (time.monotonic() - t0) * 1000

    # Log after stream completes
    await track_query(
        query=query,
        intent=intent,
        domain=effective_domain,
        retrieved_chunks=len(chunks),
        retrieval_ms=retrieval_ms,
        llm_ms=llm_ms,
        answered=bool(chunks),
        citations=len(chunks),
    )

