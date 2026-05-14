"""
Contextual Prompt Orchestration Pipeline for TiO.

This module is the single source of truth for constructing LLM prompts.
It replaces the loose _build_prompt() function in orchestrator_agent.py
with a layered, structured, grounded prompt construction system.

Pipeline layers (in order):
  1. System Identity Layer  — chatbot identity, domain, tone
  2. Site Intelligence Layer — org summary, entities, services, workflows
  3. Session Memory Layer   — history summary, active workflow, user goal
  4. Retrieval Context Layer — compressed, deduplicated, source-labeled chunks
  5. Relationship Context   — entity relationships from site profile
  6. Workflow Context Layer  — active workflow, stage, next steps
  7. External Research Layer — synthesized Tavily results (if triggered)
  8. Response Plan Layer     — deterministic goal+structure plan (no LLM call)
  9. Constraints Layer       — absolute anti-hallucination rules
 10. Conversation History   — last N turns

Key difference from prior approach:
  - No extra LLM call for response planning (deterministic instead)
  - Context compression is done without LLM (dedup + trim heuristics)
  - Tavily results are synthesized structurally (no extra LLM call)
  - Prompt is layered as structured blocks, not concatenated strings
"""

from __future__ import annotations

import re
import time
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class OrchestrationInput:
    """Everything the orchestrator needs to build a prompt."""
    query: str
    history: list[dict]
    domain: str
    intent: str
    conversation_mode: str

    # Retrieval
    chunks: list[Any]                   # RetrievedChunk objects
    retrieval_confidence: float

    # Chatbot/org context
    chatbot_name: str = "Assistant"
    chatbot_tone: str = ""
    bp_instructions: str = ""           # BehaviorProfile.instructions
    site_profile: dict = field(default_factory=dict)

    # Session context
    rolling_summary: str = ""
    active_workflow: str | None = None
    workflow_stage: str = "browsing"
    current_goal: str | None = None
    user_type: str = "new_visitor"
    session_entities: list[str] = field(default_factory=list)

    # External research
    tavily_results: list[dict] = field(default_factory=list)
    tavily_triggered: bool = False

    # Skill guidance
    skill_guidance: str = ""


@dataclass
class OrchestrationOutput:
    """The assembled prompt + metadata."""
    prompt: str
    response_plan: dict
    context_compressed: bool
    chunks_used: int
    tavily_used: bool
    prompt_tokens_est: int             # rough estimate
    orchestration_ms: float


# ---------------------------------------------------------------------------
# Context Compression (heuristic — no LLM call)
# ---------------------------------------------------------------------------

def _word_overlap(a: str, b: str) -> float:
    """Jaccard word overlap between two text snippets."""
    sa = set(a.lower().split())
    sb = set(b.lower().split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def compress_chunks(chunks: list[Any], query: str, max_tokens: int = 6000) -> tuple[str, bool]:
    """
    Compress retrieved chunks into a structured context block.

    Steps:
    1. Deduplicate near-identical chunks (Jaccard > 0.75)
    2. Score chunks by query relevance (word overlap)
    3. Trim very long chunks to their most relevant sentences
    4. Format as source-labeled blocks
    5. Hard-cap total length at max_tokens chars (rough)

    Returns (context_string, was_compressed)
    """
    if not chunks:
        return "", False

    # 1. Dedup
    unique: list[Any] = []
    for c in chunks:
        text = c.text if hasattr(c, "text") else str(c)
        duplicate = any(
            _word_overlap(text, (u.text if hasattr(u, "text") else str(u))) > 0.75
            for u in unique
        )
        if not duplicate:
            unique.append(c)

    # 2. Score by query relevance
    q_words = set(query.lower().split())

    def relevance_score(chunk) -> float:
        text = chunk.text if hasattr(chunk, "text") else str(chunk)
        chunk_words = set(text.lower().split())
        overlap = len(q_words & chunk_words) / (len(q_words) + 1e-9)
        retrieval_score = getattr(chunk, "score", 0.5)
        return overlap * 0.5 + retrieval_score * 0.5

    scored = sorted(unique, key=relevance_score, reverse=True)

    # 3. Build blocks with length tracking
    blocks: list[str] = []
    total_chars = 0
    compressed = False

    for i, chunk in enumerate(scored):
        text = chunk.text if hasattr(chunk, "text") else str(chunk)
        doc = getattr(chunk, "document", "Unknown")
        score = getattr(chunk, "score", 0.0)

        # Trim extremely long chunks to ~1200 chars, keeping sentences
        if len(text) > 1400:
            compressed = True
            sentences = re.split(r"(?<=[.!?])\s+", text)
            trimmed = []
            length = 0
            for s in sentences:
                if length + len(s) > 1200:
                    break
                trimmed.append(s)
                length += len(s)
            text = " ".join(trimmed) if trimmed else text[:1200]

        block = f"[Source {i+1} | {doc} | score={score:.3f}]\n{text}"

        if total_chars + len(block) > max_tokens * 4:  # rough char-to-token ~4:1
            compressed = True
            break

        blocks.append(block)
        total_chars += len(block)

    context = "\n\n".join(blocks)
    return context, compressed


# ---------------------------------------------------------------------------
# Tavily Result Synthesis (structural — no LLM call)
# ---------------------------------------------------------------------------

def synthesize_tavily(results: list[dict], query: str) -> str:
    """
    Convert raw Tavily results into a structured external research block.
    Extracts key sentences, deduplicates, and formats cleanly.
    Does NOT call an LLM — pure heuristic synthesis.
    """
    if not results:
        return ""

    q_words = set(query.lower().split())
    scored_snippets: list[tuple[float, str, str]] = []

    for r in results:
        url = r.get("url", "")
        title = r.get("title", "")
        text = r.get("text", "")
        if not text:
            continue

        # Score sentences by query word overlap
        sentences = re.split(r"(?<=[.!?])\s+", text)
        for sent in sentences:
            if len(sent) < 30:
                continue
            words = set(sent.lower().split())
            overlap = len(q_words & words) / (len(q_words) + 1e-9)
            scored_snippets.append((overlap, sent.strip(), url))

    if not scored_snippets:
        return ""

    # Take top 5 unique sentences
    seen: set[str] = set()
    top: list[tuple[float, str, str]] = []
    for score, sent, url in sorted(scored_snippets, key=lambda x: x[0], reverse=True):
        norm = " ".join(sent.lower().split()[:8])  # first 8 words as dedup key
        if norm not in seen:
            seen.add(norm)
            top.append((score, sent, url))
        if len(top) >= 5:
            break

    lines = ["EXTERNAL RESEARCH (synthesized from web — lower priority than indexed content):"]
    for _, sent, url in top:
        lines.append(f"- {sent} [Source: {url}]")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Deterministic Response Planner (no LLM call)
# ---------------------------------------------------------------------------

_RESPONSE_STRUCTURES: dict[str, dict] = {
    "tourism_planner": {
        "structure": "Day-by-day or Morning/Afternoon/Evening breakdown",
        "include":   ["Attractions with brief descriptions", "Pro tips", "Dining/accommodation if available"],
        "tone":      "Enthusiastic, practical",
    },
    "attraction_recommender": {
        "structure": "Numbered list of top attractions",
        "include":   ["Name, type, brief reason to visit", "Best time to go"],
        "tone":      "Descriptive, recommendation-focused",
    },
    "ride_optimizer": {
        "structure": "Prioritized ride list with tips",
        "include":   ["Wait times if known", "Skip recommendations", "Fast-pass guidance"],
        "tone":      "Practical, time-saving focused",
    },
    "course_finder": {
        "structure": "Program list with comparison",
        "include":   ["Course name, duration, eligibility", "Career paths"],
        "tone":      "Clear, student-focused",
    },
    "admission_assistant": {
        "structure": "Step-by-step admission guidance",
        "include":   ["Requirements", "Deadlines", "Documents needed", "Contact"],
        "tone":      "Direct, deadline-aware",
    },
    "scholarship_helper": {
        "structure": "Scholarship list with eligibility",
        "include":   ["Amount/type", "Eligibility criteria", "Application process"],
        "tone":      "Encouraging, practical",
    },
    "dept_navigator": {
        "structure": "Department route with contact",
        "include":   ["Department name", "Services offered", "Contact/location"],
        "tone":      "Professional, safe",
    },
    "appointment_guidance": {
        "structure": "Booking steps + contact info",
        "include":   ["How to book", "Available slots if known", "Contact details"],
        "tone":      "Clear, actionable",
    },
    "api_assistant": {
        "structure": "Overview → Code example → Notes",
        "include":   ["Auth method", "Endpoint details", "Error codes", "Code snippet"],
        "tone":      "Technical, concise",
    },
    "integration_helper": {
        "structure": "Integration steps",
        "include":   ["Setup requirements", "Step-by-step guide", "Common issues"],
        "tone":      "Technical, implementation-focused",
    },
    "shopping_guide": {
        "structure": "Product comparison or recommendation",
        "include":   ["Product name, price, key features", "Best-for summary"],
        "tone":      "Direct, comparison-focused",
    },
    "doc_summarizer": {
        "structure": "Structured summary",
        "include":   ["Key points", "Important facts", "Actionable takeaways"],
        "tone":      "Balanced, informative",
    },
}

_MODE_RESPONSE_HINTS: dict[str, str] = {
    "planning":       "Build a concrete structured plan. Use time breakdowns.",
    "troubleshooting":"Lead with the solution. Use numbered steps. Skip preamble.",
    "comparison":     "Use a comparison format. Highlight key differences.",
    "support":        "Give direct next steps. Include contact info.",
    "onboarding":     "Be welcoming. Explain with context. Avoid jargon.",
    "exploratory":    "Be informative. Suggest related topics proactively.",
}


def build_response_plan(
    query: str,
    intent: str,
    domain: str,
    conversation_mode: str,
    current_goal: str | None,
    active_workflow: str | None,
    chunks: list[Any],
    site_entities: list[str],
) -> dict:
    """
    Build a deterministic response plan without calling an LLM.
    Returns a structured dict used by the prompt builder.
    """
    structure_info = _RESPONSE_STRUCTURES.get(intent, {
        "structure": "Direct answer",
        "include":   ["Relevant facts from context", "Actionable guidance"],
        "tone":      "Clear, helpful",
    })

    # Extract key entities mentioned in chunks
    chunk_entities: list[str] = []
    for chunk in chunks[:5]:
        text = chunk.text if hasattr(chunk, "text") else ""
        # Simple: extract capitalized sequences (proper nouns heuristic)
        found = re.findall(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*\b", text)
        chunk_entities.extend(found[:5])

    # Unique, trimmed
    all_entities = list(dict.fromkeys(site_entities[:5] + chunk_entities))[:10]

    return {
        "goal":              current_goal or f"Help with: {query[:60]}",
        "workflow":          active_workflow or intent,
        "response_structure": structure_info["structure"],
        "key_inclusions":    structure_info["include"],
        "tone_hint":         structure_info["tone"],
        "mode_guidance":     _MODE_RESPONSE_HINTS.get(conversation_mode, ""),
        "contextual_entities": all_entities,
        "has_context":       len(chunks) > 0,
    }


def format_response_plan(plan: dict) -> str:
    """Format the response plan as a compact prompt block."""
    lines = [
        f"RESPONSE PLAN:",
        f"  Goal: {plan['goal']}",
        f"  Structure: {plan['response_structure']}",
        f"  Include: {'; '.join(plan['key_inclusions'])}",
        f"  Tone: {plan['tone_hint']}",
    ]
    if plan["mode_guidance"]:
        lines.append(f"  Mode: {plan['mode_guidance']}")
    if plan["contextual_entities"]:
        lines.append(f"  Key entities to reference: {', '.join(plan['contextual_entities'][:8])}")
    if not plan["has_context"]:
        lines.append("  Note: No retrieved context — answer from domain knowledge only. Do NOT fabricate specifics.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Relationship Context Builder
# ---------------------------------------------------------------------------

_RELATIONSHIP_HINTS: dict[str, dict[str, str]] = {
    "tourism": {
        "attraction_recommender": "If recommending attractions, note nearby rides/dining if available in context.",
        "tourism_planner":        "Connect attraction → zone → timing for logical flow.",
        "ride_optimizer":         "Link rides to wait times and proximity.",
    },
    "education": {
        "course_finder":          "Link department → faculty → placement outcomes.",
        "admission_assistant":    "Link admission requirements → application portal → deadlines.",
        "scholarship_helper":     "Link scholarship → eligibility → department.",
    },
    "medical": {
        "dept_navigator":         "Link symptom/concern → department → specialist → contact.",
        "appointment_guidance":   "Link appointment type → department → booking method → contact.",
        "insurance_assistant":    "Link coverage type → claim process → billing contact.",
    },
    "developer": {
        "api_assistant":          "Link API endpoint → authentication → SDK → code example.",
        "integration_helper":     "Link webhook → event type → handler → error codes.",
        "sdk_guide":              "Link SDK installation → initialization → usage → troubleshooting.",
    },
    "ecommerce": {
        "shopping_guide":         "Link product → pricing → availability → shipping/returns.",
    },
}


def build_relationship_context(
    domain: str,
    intent: str,
    site_relationships: list[str],
) -> str:
    """Build a relationship context hint for the prompt."""
    hints: list[str] = []

    # Domain + intent specific hint
    domain_hints = _RELATIONSHIP_HINTS.get(domain, {})
    intent_hint = domain_hints.get(intent, "")
    if intent_hint:
        hints.append(intent_hint)

    # Site-specific relationships from profile
    if site_relationships:
        hints.append("Known entity relationships from this site:")
        hints.extend(f"  - {r}" for r in site_relationships[:6])

    if not hints:
        return ""

    return "RELATIONSHIP CONTEXT:\n" + "\n".join(hints)


# ---------------------------------------------------------------------------
# Workflow Context Builder
# ---------------------------------------------------------------------------

_WORKFLOW_NEXT_STEPS: dict[str, dict[str, list[str]]] = {
    "admission_assistant": {
        "browsing":  ["Check admission requirements", "Review deadline calendar"],
        "planning":  ["Download application form", "Prepare documents"],
        "booking":   ["Submit application", "Pay registration fee"],
    },
    "tourism_planner": {
        "browsing":  ["Explore top attractions", "Check seasonal highlights"],
        "planning":  ["Build day-by-day itinerary", "Check opening times"],
        "booking":   ["Book tickets", "Reserve accommodation"],
    },
    "api_assistant": {
        "browsing":  ["Read authentication docs", "Explore available endpoints"],
        "planning":  ["Set up development environment", "Create API credentials"],
        "booking":   ["Test with sandbox", "Deploy to production"],
    },
    "appointment_guidance": {
        "browsing":  ["Check available departments", "View doctor profiles"],
        "booking":   ["Choose appointment slot", "Confirm booking details"],
    },
}


def build_workflow_context(
    active_workflow: str | None,
    workflow_stage: str,
    intent: str,
) -> str:
    """Build a workflow context block with next steps."""
    workflow = active_workflow or intent
    if not workflow or workflow == "general_chat":
        return ""

    stage = workflow_stage or "browsing"
    next_steps = (
        _WORKFLOW_NEXT_STEPS.get(workflow, {}).get(stage, [])
        or _WORKFLOW_NEXT_STEPS.get(intent, {}).get(stage, [])
    )

    lines = [f"WORKFLOW CONTEXT:"]
    lines.append(f"  Active: {workflow.replace('_', ' ').title()}")
    lines.append(f"  Stage: {stage}")
    if next_steps:
        lines.append(f"  Logical next steps: {', '.join(next_steps)}")
        lines.append("  Guide the user toward these next steps proactively where relevant.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Site Intelligence Layer Builder
# ---------------------------------------------------------------------------

def build_site_intelligence_block(profile: dict) -> str:
    """Format the site profile as a structured intelligence block."""
    if not profile:
        return ""

    lines = ["SITE INTELLIGENCE:"]

    summary = profile.get("site_summary", "")
    if summary:
        lines.append(f"  Organization: {summary}")

    entities = profile.get("top_entities", [])
    if entities:
        lines.append(f"  Key entities: {', '.join(str(e) for e in entities[:10])}")

    services = profile.get("key_services", [])
    if services:
        lines.append(f"  Core services: {', '.join(str(s) for s in services[:6])}")

    workflows = profile.get("workflows", [])
    if workflows:
        lines.append(f"  Available workflows: {', '.join(str(w) for w in workflows[:5])}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Session Memory Layer Builder
# ---------------------------------------------------------------------------

def build_session_memory_block(
    rolling_summary: str,
    active_workflow: str | None,
    current_goal: str | None,
    session_entities: list[str],
    conversation_mode: str,
) -> str:
    """Format session memory as a structured context block."""
    lines: list[str] = []

    if rolling_summary:
        lines.append(f"SESSION MEMORY:")
        lines.append(f"  Conversation summary: {rolling_summary[:500]}")
    if current_goal:
        lines.append(f"  User goal: {current_goal}")
    if active_workflow:
        lines.append(f"  Active workflow: {active_workflow.replace('_', ' ').title()}")
    if session_entities:
        lines.append(f"  Previously discussed: {', '.join(session_entities[:8])}")
    if conversation_mode and conversation_mode != "exploratory":
        lines.append(f"  Conversation mode: {conversation_mode}")

    if not lines:
        return ""

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Core Prompt Orchestrator
# ---------------------------------------------------------------------------

# Absolute constraints injected at highest priority
_CONSTRAINTS = """\
ABSOLUTE CONSTRAINTS (override everything above):
- NEVER use bracket placeholders: [Name], [Place], [Details], [Institution], etc.
- NEVER use robotic filler: "I'd be happy to help", "Based on the context", "As an AI", \
"Certainly!", "Of course!", "Great question!", "Let me help you with that".
- START DIRECTLY with the answer. No conversational introductions.
- Every factual claim must be grounded in RETRIEVED CONTEXT or SITE INTELLIGENCE above.
- NEVER fabricate names, prices, phone numbers, dates, or entities not in the context.
- If a specific detail is missing from context, say so naturally: \
"The indexed content doesn't specify exact [detail] — here's what I do know: ..."
- If context is from EXTERNAL RESEARCH, clearly treat it as supplementary, not primary.
- Responses must feel conversational and grounded, not like a template readout.\
"""


def build_prompt(inp: OrchestrationInput) -> OrchestrationOutput:
    """
    Assemble the full layered prompt from an OrchestrationInput.
    Returns OrchestrationOutput with the prompt + metadata.
    """
    t0 = time.monotonic()

    # --- Layer 4: Context Compression ---
    compressed_context, was_compressed = compress_chunks(inp.chunks, inp.query)

    # --- Layer 7: External Research ---
    tavily_block = ""
    if inp.tavily_triggered and inp.tavily_results:
        tavily_block = synthesize_tavily(inp.tavily_results, inp.query)

    # --- Layer 8: Response Plan (deterministic) ---
    site_entities = inp.site_profile.get("top_entities", []) if inp.site_profile else []
    response_plan = build_response_plan(
        query=inp.query,
        intent=inp.intent,
        domain=inp.domain,
        conversation_mode=inp.conversation_mode,
        current_goal=inp.current_goal,
        active_workflow=inp.active_workflow,
        chunks=inp.chunks,
        site_entities=site_entities if isinstance(site_entities, list) else [],
    )
    plan_block = format_response_plan(response_plan)

    # --- Layer 1: System Identity ---
    identity_block = (
        f"SYSTEM IDENTITY:\n"
        f"  Chatbot: {inp.chatbot_name}\n"
        f"  Domain: {inp.domain}\n"
        f"  Mode: {inp.conversation_mode}\n"
        f"  Tone: {inp.chatbot_tone or 'Professional and helpful'}"
    )

    # --- Layer 2: Site Intelligence ---
    site_block = build_site_intelligence_block(inp.site_profile or {})

    # --- Layer 3: Session Memory ---
    session_block = build_session_memory_block(
        rolling_summary=inp.rolling_summary,
        active_workflow=inp.active_workflow,
        current_goal=inp.current_goal,
        session_entities=inp.session_entities,
        conversation_mode=inp.conversation_mode,
    )

    # --- Layer 5: Relationship Context ---
    relationship_block = build_relationship_context(
        domain=inp.domain,
        intent=inp.intent,
        site_relationships=inp.site_profile.get("relationships", []) if inp.site_profile else [],
    )

    # --- Layer 6: Workflow Context ---
    workflow_block = build_workflow_context(
        active_workflow=inp.active_workflow,
        workflow_stage=inp.workflow_stage,
        intent=inp.intent,
    )

    # --- Skill guidance ---
    skill_block = f"SKILL GUIDANCE: {inp.skill_guidance}" if inp.skill_guidance else ""

    # --- Confidence note ---
    confidence_block = ""
    if inp.retrieval_confidence < 0.35:
        confidence_block = (
            f"RETRIEVAL NOTE: Local retrieval confidence is low ({inp.retrieval_confidence:.0%}). "
            "Rely on Site Intelligence and external research for grounding. "
            "Be honest about what is and isn't confirmed."
        )

    # --- Assemble system prompt from ordered blocks ---
    system_layers = [
        inp.bp_instructions,   # Domain behavior profile (base instructions + domain rules)
        identity_block,
        site_block,
        session_block,
        relationship_block,
        workflow_block,
        skill_block,
        confidence_block,
        plan_block,
    ]
    system_content = "\n\n".join(b for b in system_layers if b.strip())

    # --- Build final prompt string ---
    parts: list[str] = [f"SYSTEM:\n{system_content}"]

    # Retrieved context block (Layer 4)
    if compressed_context:
        parts.append(f"RETRIEVED CONTEXT:\n{compressed_context}")
    elif not inp.tavily_triggered:
        parts.append(
            "RETRIEVED CONTEXT: No relevant content found in the knowledge base for this query. "
            "Answer from Site Intelligence and domain knowledge only. "
            "Do NOT fabricate specific names, prices, or details."
        )

    # External research (Layer 7)
    if tavily_block:
        parts.append(tavily_block)

    # Constraints (always last in system section)
    parts.append(_CONSTRAINTS)

    # Conversation history (last N turns)
    history_turns = inp.history[-8:]
    for turn in history_turns:
        role = turn.get("role", "user").upper()
        content = turn.get("content", "")
        parts.append(f"{role}: {content}")

    # User query
    parts.append(f"USER: {inp.query}")
    parts.append("ASSISTANT:")

    prompt = "\n\n".join(parts)

    orchestration_ms = (time.monotonic() - t0) * 1000
    prompt_tokens_est = len(prompt) // 4  # rough 4 chars per token

    logger.info(
        f"[PROMPT ORCHESTRATOR] domain={inp.domain} intent={inp.intent} "
        f"chunks={len(inp.chunks)} compressed={was_compressed} "
        f"tavily={inp.tavily_triggered} tokens_est={prompt_tokens_est} "
        f"time={orchestration_ms:.1f}ms"
    )

    return OrchestrationOutput(
        prompt=prompt,
        response_plan=response_plan,
        context_compressed=was_compressed,
        chunks_used=len(inp.chunks),
        tavily_used=inp.tavily_triggered and bool(inp.tavily_results),
        prompt_tokens_est=prompt_tokens_est,
        orchestration_ms=orchestration_ms,
    )
