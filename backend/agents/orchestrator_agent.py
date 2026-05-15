"""
Orchestrator — the intelligence core of TiO.

Contextual Prompt Orchestration Pipeline (v2):
  Uses backend.orchestration.prompt_orchestrator for structured, layered
  prompt construction. Eliminates the extra LLM planning call.

Pipeline per request:
  1.  Input sanitization
  2.  Session isolation (security)
  3.  Domain detection with confidence
  4.  Intent detection (keyword + semantic)
  5.  Query expansion
  6.  Vector retrieval (RRF + reranking, chatbot-scoped)
  7.  Confidence scoring
  8.  Goal memory + rolling summary update
  9.  Site intelligence loading
  10. Workflow-aware re-retrieval (if needed)
  11. Tavily external research (if confidence < threshold)
  12. Prompt orchestration (layered, deterministic — no extra LLM call)
    13. LLM generation (Ollama local inference)
    14. Response sanitization
  15. Monitoring + tracking
"""

import asyncio
import time
import logging
import re
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
from backend.utils.query_expander import expand_query
from backend.utils.goal_memory import update_goal, get_or_create_goal
from backend.utils.confidence import build_confidence_report, build_fallback_message
from backend.utils.site_intelligence import get_site_context_string
from backend.memory.service import update_rolling_summary
from backend.orchestration.prompt_orchestrator import (
    OrchestrationInput, build_prompt,
)
from backend.synthesis.context_aggregator import ContextAggregator
from backend.synthesis.workflow_engine import WorkflowEngine
from backend.synthesis.context_compressor import ContextCompressor
from backend.synthesis.response_planner import ResponsePlanner
from backend.synthesis.response_sanitizer import ResponseSanitizer


logger = logging.getLogger(__name__)
settings = get_settings()

# Synthesis Engines
context_aggregator = ContextAggregator()
workflow_engine = WorkflowEngine()
context_compressor = ContextCompressor()
response_planner_v2 = ResponsePlanner()
response_sanitizer = ResponseSanitizer()


# ---------------------------------------------------------------------------
# ROBOTIC PHRASE FILTER
# ---------------------------------------------------------------------------

_ROBOTIC_PHRASES = [
    r"i['']d be happy to help",
    r"i['']m happy to assist",
    r"i['']m here to help",
    r"as an ai",
    r"as a language model",
    r"based on the (?:retrieved )?context[,.]?",
    r"based on the (?:provided )?information[,.]?",
    r"based on what i(?:'ve| have) found[,.]?",
    r"could you (?:please )?clarify\??",
    r"could you (?:please )?specify\??",
    r"please (?:note that )?i cannot provide",
    r"i (?:must |need to )?clarify that",
    r"it['']s important to note that",
    r"please be aware that",
    r"i (?:do not|don['']t) have access to real.?time",
    r"i (?:am|'m) unable to provide",
    r"of course[,!]? (?:here|let me)",
    r"certainly[,!]? (?:here|let me|i)",
    r"absolutely[,!]? (?:here|let me|i)",
    r"great question[,!]?",
    r"sure[,!]? (?:here|let me|i)",
    r"let me help you with that",
    r"i understand(?: your question)?[,.]?",
    r"thank you for (?:asking|your question)[,.]?",
]

_ROBOTIC_RE = [re.compile(p, re.IGNORECASE) for p in _ROBOTIC_PHRASES]


def _strip_robotic_phrases(text: str) -> str:
    for pattern in _ROBOTIC_RE:
        text = pattern.sub("", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"^\s*[,.:!]\s*", "", text)
    return text.strip()


def _has_placeholders(text: str) -> bool:
    return bool(re.search(r'\[[A-Z][^\]]{2,40}\]', text))


def _strip_placeholders(text: str) -> str:
    return re.sub(r'\[[A-Z][^\]]{2,40}\]', 'relevant content', text)


# ---------------------------------------------------------------------------
# INTENT DETECTION
# ---------------------------------------------------------------------------

INTENT_PATTERNS: dict[str, list[str]] = {
    "tourism_planner":          ["plan", "itinerary", "trip", "travel", "visit", "schedule", "route", "weekend"],
    "attraction_recommender":   ["attractions", "things to do", "places to see", "must see", "popular", "best places"],
    "ride_optimizer":           ["wait time", "queue", "rides", "skip the line", "fast pass", "thrill"],
    "course_finder":            ["course", "program", "major", "degree", "study", "curriculum", "syllabus"],
    "admission_assistant":      ["admission", "apply", "enroll", "deadline", "requirements", "eligibility"],
    "scholarship_helper":       ["scholarship", "financial aid", "grant", "funding", "bursary", "fees"],
    "dept_navigator":           ["department", "specialist", "pain", "symptom", "doctor", "consult", "hospital"],
    "appointment_guidance":     ["appointment", "book", "schedule", "visiting hours", "contact", "reserve"],
    "insurance_assistant":      ["insurance", "coverage", "billing", "payment", "claims", "premium"],
    "api_assistant":            ["api", "sdk", "code", "endpoint", "authenticate", "bearer", "token", "rest"],
    "integration_helper":       ["integrate", "integration", "webhook", "event", "flow", "setup", "connect"],
    "sdk_guide":                ["install", "library", "npm", "pip", "package", "init", "import"],
    "shopping_guide":           ["product", "buy", "price", "pricing", "catalog", "compare", "best", "order"],
    "doc_summarizer":           ["summarize", "summary", "overview", "what is this", "tell me about", "highlights"],
}

DOMAIN_SKILL_MAP: dict[str, list[str]] = {
    "tourism":   ["tourism_planner", "attraction_recommender", "ride_optimizer", "doc_summarizer"],
    "education": ["course_finder", "admission_assistant", "scholarship_helper", "doc_summarizer"],
    "medical":   ["dept_navigator", "appointment_guidance", "insurance_assistant", "doc_summarizer"],
    "developer": ["api_assistant", "integration_helper", "sdk_guide", "doc_summarizer"],
    "ecommerce": ["shopping_guide", "doc_summarizer"],
    "general":   ["doc_summarizer"],
}


def detect_intent(query: str, domain: str | None) -> tuple[str, int, float]:
    q = query.lower()
    if domain and domain != "general":
        eligible = DOMAIN_SKILL_MAP.get(domain, ["doc_summarizer"])
    else:
        eligible = list(INTENT_PATTERNS.keys())

    scores: dict[str, int] = {skill: 0 for skill in eligible}
    for skill in eligible:
        for kw in INTENT_PATTERNS.get(skill, []):
            if kw in q:
                scores[skill] += 1

    best_kw_skill = max(scores, key=scores.get, default="doc_summarizer")
    kw_score = scores.get(best_kw_skill, 0)
    if kw_score > 0:
        return best_kw_skill, kw_score, 0.6

    sem_intent = intent_intelligence.detect(query, eligible_skills=eligible)
    return sem_intent, 0, 0.5


# ---------------------------------------------------------------------------
# PROACTIVE SUGGESTION ENGINE
# ---------------------------------------------------------------------------

def get_proactive_suggestions(domain: str, intent: str, goal: str | None = None) -> list[str]:
    base_suggestions = {
        "tourism":   ["Tell me about top attractions", "Plan a 3-day itinerary", "Show local hotels"],
        "education": ["View admission requirements", "Find available scholarships", "Browse course catalog"],
        "medical":   ["Book an appointment", "Find a specialist", "View insurance coverage"],
        "developer": ["Show API authentication", "View integration guide", "Download SDK"],
        "ecommerce": ["View latest offers", "Track my order", "Check return policy"],
        "general":   ["Summarize this site", "What services are offered?", "Contact support"],
    }
    intent_suggestions = {
        "tourism_planner":     ["Add child-friendly spots", "Suggest budget options", "Check weather for my trip"],
        "admission_assistant": ["Check deadline for fall semester", "Required documents", "Contact admissions"],
        "api_assistant":       ["Show cURL examples", "View error codes", "Check rate limits"],
    }
    res = intent_suggestions.get(intent, [])
    if not res:
        res = base_suggestions.get(domain, base_suggestions["general"])
    return res[:3]


# ---------------------------------------------------------------------------
# CONTEXT RETRIEVAL
# ---------------------------------------------------------------------------

async def _get_context(
    query: str,
    chatbot_id: int | None,
    domain: str | None = None,
    workflow: str | None = None,
    active_entities: list[str] | None = None,
    user_goal: str | None = None,
) -> tuple[list, float]:
    t0 = time.monotonic()
    chunks = await async_retrieve(
        query, top_k=settings.top_k, chatbot_id=chatbot_id, 
        domain=domain, workflow=workflow,
        active_entities=active_entities,
        user_goal=user_goal
    )
    elapsed_ms = (time.monotonic() - t0) * 1000

    if chatbot_id:
        before = len(chunks)
        chunks = [c for c in chunks if c.metadata.get("chatbot_id") == chatbot_id]
        filtered = before - len(chunks)
        if filtered > 0:
            logger.warning(f"[SECURITY] Filtered {filtered} cross-chatbot chunks for chatbot_id={chatbot_id}")

    return chunks, elapsed_ms


# ---------------------------------------------------------------------------
# CHATBOT LOOKUP + SESSION ISOLATION
# ---------------------------------------------------------------------------

async def _get_chatbot(
    db: AsyncSession,
    chatbot_id: int | None = None,
    session_id: str | None = None,
) -> "Chatbot | None":
    chatbot = None
    if chatbot_id:
        chatbot = await db.get(Chatbot, chatbot_id)

    if session_id and chatbot_id:
        stmt = select(Conversation).where(
            Conversation.session_id == session_id,
            Conversation.chatbot_id == chatbot_id,
        )
        conv = (await db.execute(stmt)).scalar_one_or_none()
        if conv is None:
            other = (await db.execute(
                select(Conversation).where(Conversation.session_id == session_id)
            )).scalar_one_or_none()
            if other and other.chatbot_id != chatbot_id:
                logger.error(
                    f"[SECURITY] Session isolation violation: session={session_id} "
                    f"belongs to chatbot={other.chatbot_id}, requested={chatbot_id}. Denying."
                )
                return None

    return chatbot


# ---------------------------------------------------------------------------
# DOMAIN DETECTION
# ---------------------------------------------------------------------------

def _detect_domain_with_confidence(
    query: str, chatbot: "Chatbot | None"
) -> tuple[str, float]:
    chatbot_domain = chatbot.domain if chatbot else None
    if chatbot_domain and chatbot_domain != "general":
        return chatbot_domain, 0.95

    detected_domain = domain_detector.detect(query, {"url": chatbot.website_url if chatbot else ""})
    scores = domain_detector.get_scores(query, {"url": chatbot.website_url if chatbot else ""})
    if not scores:
        return "general", 0.3

    sorted_scores = sorted(scores, key=lambda x: x.score, reverse=True)
    top = sorted_scores[0]
    second = sorted_scores[1].score if len(sorted_scores) > 1 else 0.0
    gap = (top.score - second) / (top.score + 1e-9)
    conf = min(0.4 + gap * 0.5, 0.95) if top.score > 1.0 else 0.3
    return detected_domain, round(conf, 2)


# ---------------------------------------------------------------------------
# POST-PROCESSING
# ---------------------------------------------------------------------------

def _post_process_answer(answer: str) -> tuple[str, bool]:
    had_warning = False
    
    # Use the humanization layer
    answer = response_sanitizer.humanize(answer)
    
    answer = sanitize_output(answer)
    if _has_placeholders(answer):
        had_warning = True
        logger.warning("[ORCHESTRATOR] Bracket placeholder detected — stripping.")
        answer = _strip_placeholders(answer)
        if _has_placeholders(answer):
            answer = (
                "The specific details for that query weren't clearly identified in the site content. "
                "I can provide a general overview instead — what would you like to know more about?"
            )
    return answer, had_warning


# ---------------------------------------------------------------------------
# TAVILY SEARCH (with retry + timeout)
# ---------------------------------------------------------------------------

async def _fetch_tavily(query: str, chatbot_website: str | None = None) -> list[dict]:
    """
    Fetch Tavily results with strict retry + timeout protection.
    Tavily is ONLY for runtime chat augmentation, never used during ingestion.
    """
    from backend.llm.tavily_client import tavily_client
    from backend.utils.api_usage_tracker import track_api_call

    # Security: Ensure no external search runs if API key is missing
    if not settings.tavily_api_key:
        return []

    scoped_query = query
    if chatbot_website:
        from urllib.parse import urlparse
        domain = urlparse(chatbot_website).netloc.replace("www.", "")
        if domain:
            scoped_query = f"site:{domain} {query}"

    MAX_ATTEMPTS = 2
    TIMEOUT = 10.0  # 10s hard timeout per attempt

    for attempt in range(MAX_ATTEMPTS):
        try:
            # 1. Protect with asyncio.wait_for
            results = await asyncio.wait_for(
                tavily_client.search(scoped_query, search_depth="basic", max_results=5),
                timeout=TIMEOUT,
            )
            
            # 2. Track usage and return
            if results:
                track_api_call("tavily")
                logger.info(f"[TAVILY] {len(results)} results for query={query[:50]!r} (attempt {attempt+1})")
                return results
            
            # If no results, don't bother retrying
            return []

        except asyncio.TimeoutError:
            logger.warning(f"[TAVILY] Timeout ({TIMEOUT}s) for query={query[:50]!r} on attempt {attempt+1}")
        except Exception as e:
            logger.error(f"[TAVILY] Unexpected error on attempt {attempt+1}: {type(e).__name__}: {e}")
        
        # Exponential backoff for retry
        if attempt < MAX_ATTEMPTS - 1:
            wait_time = 1.0 * (attempt + 1)
            await asyncio.sleep(wait_time)

    # 3. Graceful Fallback: Return empty list so pipeline continues with local knowledge
    return []


# ---------------------------------------------------------------------------
# SHARED PIPELINE CORE
# (used by both run_orchestration and run_orchestration_stream)
# ---------------------------------------------------------------------------

async def _run_pipeline(
    query: str,
    history: list[dict],
    db: AsyncSession,
    chatbot_id: int | None = None,
    session_id: str | None = None,
    domain: str | None = None,
    profile: str | None = None,
) -> tuple[OrchestrationInput, dict, float]:
    """
    Runs everything up to (but not including) LLM generation.
    Returns (orchestration_input, confidence_report_dict, retrieval_ms).
    """
    from backend.utils.api_usage_tracker import track_api_call

    # 1. Sanitize
    query = sanitize_input(query)

    # 2. Session isolation
    chatbot = await _get_chatbot(db, chatbot_id, session_id)
    if chatbot is None and chatbot_id:
        raise ValueError("session_isolation_failed")

    effective_id = chatbot.id if chatbot else None

    # 3. Domain detection
    effective_domain, domain_conf = _detect_domain_with_confidence(query, chatbot)
    if domain:
        effective_domain = domain
        domain_conf = 0.95

    # 4. Intent detection
    intent, kw_score, sem_score = detect_intent(query, effective_domain)

    # 5. Query expansion
    expanded_query = expand_query(query, domain=effective_domain)
    if expanded_query != query.lower():
        logger.debug(f"[EXPAND] '{query}' -> '{expanded_query}'")

    # 6. Retrieval
    # Load session state for workflow-aware retrieval
    active_entities: list[str] = []
    user_goal: str | None = None
    active_workflow: str | None = None
    
    if session_id and effective_id:
        from backend.utils.goal_memory import get_or_create_goal
        goal_obj = await get_or_create_goal(db, session_id, effective_id)
        if goal_obj:
            active_entities = (goal_obj.state_json or {}).get("discovered_entities", [])
            user_goal = goal_obj.current_goal
            active_workflow = goal_obj.active_workflow

    chunks, retrieval_ms = await _get_context(
        expanded_query, effective_id, 
        domain=effective_domain,
        workflow=active_workflow,
        active_entities=active_entities,
        user_goal=user_goal
    )

    # 7. Confidence scoring
    from backend.utils.domain_intelligence import domain_detector as _dd
    domain_scores = _dd.get_scores(query, {"url": chatbot.website_url if chatbot else ""})
    confidence = build_confidence_report(
        chunks=chunks, query=query, domain=effective_domain, intent=intent,
        keyword_score=kw_score, semantic_score=sem_score, detected_scores=domain_scores,
    )

    # 8. Goal memory + rolling summary
    goal = None
    rolling_summary = ""
    if session_id and effective_id:
        from backend.memory.service import get_conversation_by_session
        conv = await get_conversation_by_session(db, session_id, effective_id)
        goal = await update_goal(db, session_id, effective_id, query, intent, domain=effective_domain)
        if conv:
            rolling_summary = await update_rolling_summary(db, conv.id)

    # 9. Site intelligence
    site_profile: dict = {}
    if chatbot and chatbot.site_profile:
        site_profile = chatbot.site_profile

    # 10. Workflow-aware re-retrieval (if first pass empty)
    if goal and goal.active_workflow and not chunks:
        chunks, _ = await _get_context(
            expanded_query, effective_id,
            domain=effective_domain, workflow=goal.active_workflow,
        )

    # --- SYNTHESIS LAYER (New) ---
    # A. Aggregate Context
    snapshot = context_aggregator.aggregate(chunks, query, site_profile)
    
    # B. Synthesize Workflow & Continuity
    synthesized_workflow = workflow_engine.synthesize_workflow(query, intent, goal, history)
    
    # C. Meaning Synthesis (Context Compression)
    synthesized_meaning = await context_compressor.synthesize_meaning(chunks, query, effective_domain)
    
    # D. Advanced Response Planning
    raw_plan = response_planner_v2.plan(query, snapshot, synthesized_workflow, effective_domain)
    response_plan_dict = {
        "goal": raw_plan.get("goal", ""),
        "workflow": raw_plan.get("workflow", ""),
        "response_structure": raw_plan.get("response_structure", "conversational"),
        "steps": raw_plan.get("steps", []),
        "reasoning": raw_plan.get("reasoning", ""),
        "recommendations": raw_plan.get("recommendations", [])
    }
    logger.info(f"[ORCH DEBUG] Generated plan keys: {list(response_plan_dict.keys())}")

    # 11. Tavily external research (if low confidence)
    tavily_results: list[dict] = []
    tavily_triggered = False
    if not chunks or (confidence.retrieval_confidence < 0.3 and len(query.split()) > 3):
        tavily_triggered = True
        tavily_results = await _fetch_tavily(query, chatbot.website_url if chatbot else None)
        logger.info(
            f"[ORCHESTRATOR] Tavily triggered (confidence={confidence.retrieval_confidence:.2f}), "
            f"got {len(tavily_results)} results"
        )

    # 12. LLM API tracking
    track_api_call("ollama")

    # 13. Build OrchestrationInput
    bp = get_profile(profile or effective_domain)
    skill_guidance = get_skill_guidance(intent)

    session_entities = snapshot.entities # Use synthesized entities

    orch_input = OrchestrationInput(
        query=query,
        history=history,
        domain=effective_domain,
        intent=intent,
        conversation_mode=goal.conversation_mode if goal else "exploratory",
        chunks=chunks,
        retrieval_confidence=confidence.retrieval_confidence,
        chatbot_name=chatbot.name if chatbot else "Assistant",
        chatbot_tone=bp.tone,
        bp_instructions=bp.instructions,
        site_profile=site_profile,
        rolling_summary=rolling_summary,
        active_workflow=synthesized_workflow.active_workflow,
        workflow_stage=synthesized_workflow.current_stage,
        current_goal=synthesized_workflow.active_goal,
        user_type=(goal.state_json or {}).get("user_type", "new_visitor") if goal else "new_visitor",
        session_entities=session_entities,
        tavily_results=tavily_results,
        tavily_triggered=tavily_triggered,
        skill_guidance=skill_guidance,
        context_snapshot=snapshot,
        synthesized_workflow=synthesized_workflow,
        synthesized_meaning=synthesized_meaning,
        response_plan_dict=response_plan_dict,
    )

    conf_dict = {
        "retrieval_confidence": confidence.retrieval_confidence,
        "overall": confidence.overall,
        "should_infer": confidence.should_infer,
        "fallback_reason": confidence.fallback_reason,
        "domain_conf": domain_conf,
        "intent": intent,
        "domain": effective_domain,
        "kw_score": kw_score,
        "sem_score": sem_score,
        "effective_id": effective_id,
        "bp": bp,
        "goal": goal,
        "confidence_obj": confidence,
    }

    return orch_input, conf_dict, retrieval_ms


# ---------------------------------------------------------------------------
# PUBLIC API — Non-streaming (HTTP /chat)
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

    # Pipeline
    try:
        orch_input, conf, retrieval_ms = await _run_pipeline(
            query=query, history=history, db=db,
            chatbot_id=chatbot_id, session_id=session_id,
            domain=domain, profile=profile,
        )
    except ValueError as e:
        if "session_isolation_failed" in str(e):
            return {
                "answer": "Session error: unable to verify chatbot identity. Please refresh and try again.",
                "citations": [], "intent": "error", "domain": "general", "profile": "general",
            }
        logger.error(f"[ORCH ERROR] ValueError in pipeline: {e}", exc_info=True)
        return {
            "answer": "I encountered an internal planning error, but I'll do my best to help. How can I assist you?",
            "citations": [], "intent": "error", "domain": "general", "profile": "general", "confidence": 0.0
        }
    except Exception as e:
        logger.error(f"[ORCH ERROR] Unexpected error in pipeline: {e}", exc_info=True)
        return {
            "answer": "I'm having trouble processing that right now. How else can I help?",
            "citations": [], "intent": "error", "domain": "general", "profile": "general", "confidence": 0.0
        }

    goal = conf["goal"]
    bp = conf["bp"]
    confidence = conf["confidence_obj"]
    intent = conf["intent"]
    effective_domain = conf["domain"]

    # Graceful fallback if no content at all
    if not orch_input.chunks and not orch_input.tavily_results and not confidence.should_infer:
        fallback_msg = build_fallback_message(confidence, effective_domain)
        return {
            "answer": fallback_msg,
            "citations": [],
            "intent": intent,
            "suggestions": bp.suggestions,
            "domain": effective_domain,
            "profile": bp.name,
            "confidence": confidence.overall,
        }

    # Build layered prompt
    orch_output = build_prompt(orch_input)

    # LLM generation
    t0 = time.monotonic()
    raw_answer = await ollama_client.generate(orch_output.prompt, model=settings.ollama_model)
    llm_ms = (time.monotonic() - t0) * 1000

    # Post-process
    answer, had_warning = _post_process_answer(raw_answer)

    # Track
    await track_query(
        query=query,
        intent=intent,
        domain=effective_domain,
        retrieved_chunks=len(orch_input.chunks),
        retrieval_ms=retrieval_ms,
        llm_ms=llm_ms,
        answered=bool(orch_input.chunks or orch_input.tavily_results),
        confidence=confidence.overall,
        fallback=not confidence.should_infer,
        hallucination_warning=had_warning,
        conversation_mode=goal.conversation_mode if goal else "exploratory",
        domain_mismatch=conf["domain_conf"] < 0.4,
    )

    # Monitoring for orchestration quality
    logger.info(
        f"[ORCH] prompt_tokens={orch_output.prompt_tokens_est} "
        f"orch_ms={orch_output.orchestration_ms:.1f} llm_ms={llm_ms:.0f} "
        f"tavily={orch_output.tavily_used} compressed={orch_output.context_compressed}"
    )

    suggestions = get_proactive_suggestions(effective_domain, intent, goal.current_goal if goal else None)

    return {
        "answer": answer,
        "citations": [c.__dict__ for c in orch_input.chunks],
        "intent": intent,
        "suggestions": suggestions if not history else [],
        "domain": effective_domain,
        "profile": bp.name,
        "confidence": confidence.overall,
        "goal": goal.current_goal if goal else None,
        "conversation_mode": goal.conversation_mode if goal else "exploratory",
        "response_plan": orch_output.response_plan,
        "tavily_used": orch_output.tavily_used,
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
    # Pipeline
    try:
        orch_input, conf, retrieval_ms = await _run_pipeline(
            query=query, history=history, db=db,
            chatbot_id=chatbot_id, session_id=session_id,
        )
    except ValueError as e:
        if "session_isolation_failed" in str(e):
            yield {"type": "error", "content": "Session isolation: chatbot identity mismatch. Please refresh."}
            return
        logger.error(f"[ORCH ERROR] ValueError in stream pipeline: {e}", exc_info=True)
        yield {"type": "token", "content": "I encountered an internal planning error, but I'll do my best to help. "}
        yield {"type": "final", "answer": "I encountered an internal planning error, but I'll do my best to help. ", "citations": [], "confidence": 0.0}
        return
    except Exception as e:
        logger.error(f"[ORCH ERROR] Unexpected error in stream pipeline: {e}", exc_info=True)
        yield {"type": "token", "content": "I'm having trouble processing that right now. How else can I help?"}
        yield {"type": "final", "answer": "I'm having trouble processing that right now. How else can I help?", "citations": [], "confidence": 0.0}
        return

    goal = conf["goal"]
    bp = conf["bp"]
    confidence = conf["confidence_obj"]
    intent = conf["intent"]
    effective_domain = conf["domain"]

    # Emit metadata immediately
    yield {
        "type": "metadata",
        "citations": [c.__dict__ for c in orch_input.chunks],
        "intent": intent,
        "domain": effective_domain,
        "confidence": confidence.overall,
        "conversation_mode": goal.conversation_mode if goal else "exploratory",
        "goal": goal.current_goal if goal else None,
        "tavily_triggered": orch_input.tavily_triggered,
    }

    # High-level pipeline observation
    yield {"type": "thought", "content": f"Intent: {intent} ({effective_domain} domain)"}
    yield {"type": "thought", "content": f"Retrieval: Found {len(orch_input.chunks)} relevant knowledge chunks."}
    
    if orch_input.tavily_triggered:
        yield {"type": "thought", "content": f"Low local confidence. Triggered external research via Tavily ({len(orch_input.tavily_results)} results)."}

    yield {"type": "thought", "content": "Synthesizing multi-page context and resolving entity relationships..."}
    # (Context was already aggregated in _run_pipeline, we just report it here)
    
    if orch_input.synthesized_workflow.active_workflow:
        yield {"type": "thought", "content": f"Workflow detected: {orch_input.synthesized_workflow.active_workflow} (Stage: {orch_input.synthesized_workflow.current_stage})"}
    
    yield {"type": "thought", "content": "Generating response plan based on synthesized meaning..."}

    # Graceful fallback
    if not orch_input.chunks and not orch_input.tavily_results and not confidence.should_infer:
        fallback_msg = build_fallback_message(confidence, effective_domain)
        yield {"type": "token", "content": fallback_msg}
        yield {"type": "final", "answer": fallback_msg, "citations": [], "confidence": confidence.overall}
        return

    # Build layered prompt
    orch_output = build_prompt(orch_input)

    # Emit response plan as thought (for transparency in UI)
    plan = orch_output.response_plan
    thought = (
        f"Goal: {plan.get('goal', '')} | "
        f"Structure: {plan.get('response_structure', 'conversational')} | "
        f"Workflow: {plan.get('workflow', '')}"
    )
    yield {"type": "thought", "content": thought}

    # Stream generation
    t0 = time.monotonic()
    full_answer = ""
    async for token in ollama_client.generate_stream(orch_output.prompt, model=settings.ollama_model):
        full_answer += token
        yield {"type": "token", "content": token}

    llm_ms = (time.monotonic() - t0) * 1000

    # Post-process
    cleaned, had_warning = _post_process_answer(full_answer)

    # Track
    await track_query(
        query=query,
        intent=intent,
        domain=effective_domain,
        retrieved_chunks=len(orch_input.chunks),
        retrieval_ms=retrieval_ms,
        llm_ms=llm_ms,
        answered=bool(orch_input.chunks or orch_input.tavily_results),
        confidence=confidence.overall,
        fallback=not confidence.should_infer,
        hallucination_warning=had_warning,
        conversation_mode=goal.conversation_mode if goal else "exploratory",
        domain_mismatch=conf["domain_conf"] < 0.4,
    )

    logger.info(
        f"[ORCH STREAM] prompt_tokens={orch_output.prompt_tokens_est} "
        f"orch_ms={orch_output.orchestration_ms:.1f} llm_ms={llm_ms:.0f} "
        f"tavily={orch_output.tavily_used}"
    )

    suggestions = get_proactive_suggestions(effective_domain, intent, goal.current_goal if goal else None)
    yield {
        "type": "final",
        "answer": cleaned,
        "citations": [c.__dict__ for c in orch_input.chunks],
        "confidence": confidence.overall,
        "suggestions": suggestions if not history else [],
        "goal": goal.current_goal if goal else None,
        "response_plan": orch_output.response_plan,
        "tavily_used": orch_output.tavily_used,
    }

