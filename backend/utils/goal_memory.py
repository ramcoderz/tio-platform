"""
User Goal Memory — tracks persistent session goals and workflow state in the database.
"""

import re
import logging
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.entities import ConversationGoal
from datetime import datetime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mode & Stage detection heuristics
# ---------------------------------------------------------------------------

_MODE_PATTERNS: dict[str, list[str]] = {
    "planning": [r"\bplan\b", r"\bitinerary\b", r"\bschedule\b", r"\btrip\b", r"\bweekend\b"],
    "troubleshooting": [r"\berror\b", r"\bnot working\b", r"\bfailed\b", r"\bproblem\b", r"\bissue\b"],
    "comparison": [r"\bvs\b", r"\bversus\b", r"\bcompare\b", r"\bdifference\b"],
    "support": [r"\bhelp\b", r"\bneed assistance\b", r"\bcontact\b", r"\bbook\b"],
    "onboarding": [r"\bhow do i start\b", r"\bget started\b", r"\bbeginners?\b", r"\bfirst time\b"],
}

_STAGE_PATTERNS: dict[str, list[str]] = {
    "planning":       [r"\bplan\b", r"\bschedule\b", r"\bitinerary\b"],
    "booking":        [r"\bbook\b", r"\breserve\b", r"\bpurchase\b", r"\bbuy\b"],
    "comparing":      [r"\bcompare\b", r"\bvs\b", r"\bdifference\b"],
    "troubleshooting":[r"\berror\b", r"\bproblem\b", r"\bnot working\b"],
}

def detect_conversation_mode(query: str) -> str:
    q = query.lower()
    for mode, patterns in _MODE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, q):
                return mode
    return "exploratory"

def detect_workflow_stage(query: str) -> str:
    q = query.lower()
    for stage, patterns in _STAGE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, q):
                return stage
    return "browsing"

def infer_goal(query: str, domain: Optional[str]) -> str:
    """Infer a human-readable goal from the user's message and domain."""
    q = query.lower()
    if domain == "tourism":
        if any(w in q for w in ["plan", "itinerary"]): return "Plan a visit"
        if any(w in q for w in ["ride", "attraction"]): return "Find activities"
    elif domain == "education":
        if any(w in q for w in ["apply", "admission"]): return "Apply for admission"
    elif domain == "developer":
        if any(w in q for w in ["api", "connect"]): return "Integrate API"
    return f"Get help with: {query[:50]}"

# ---------------------------------------------------------------------------
# Persistent Goal Operations
# ---------------------------------------------------------------------------

async def get_or_create_goal(db: AsyncSession, session_id: str, chatbot_id: int) -> ConversationGoal:
    stmt = select(ConversationGoal).where(
        ConversationGoal.session_id == session_id,
        ConversationGoal.chatbot_id == chatbot_id
    )
    goal = (await db.execute(stmt)).scalar_one_or_none()
    if not goal:
        goal = ConversationGoal(session_id=session_id, chatbot_id=chatbot_id)
        db.add(goal)
        await db.flush()
    return goal

async def update_goal(
    db: AsyncSession, 
    session_id: str, 
    chatbot_id: int, 
    query: str, 
    intent: str, 
    domain: Optional[str] = None
) -> ConversationGoal:
    """Updates the persistent goal state on every message."""
    goal = await get_or_create_goal(db, session_id, chatbot_id)
    
    # Update mode and stage
    goal.conversation_mode = detect_conversation_mode(query)
    stage = detect_workflow_stage(query)
    if stage != "browsing":
        goal.workflow_stage = stage
        
    # Update active workflow based on intent
    if intent and intent != "general_chat":
        goal.active_workflow = intent
        
    # Update inferred goal if current one is generic
    new_goal = infer_goal(query, domain)
    if not goal.current_goal or "Get help with:" in goal.current_goal:
        goal.current_goal = new_goal

    # Track message count in state_json
    state = goal.state_json or {}
    state["message_count"] = state.get("message_count", 0) + 1
    
    # Track discovered entities (placeholder for integration with entity extractor)
    # state["discovered_entities"] = list(set(state.get("discovered_entities", []) + extracted_entities))
    
    goal.state_json = state
    goal.updated_at = datetime.utcnow()
    
    await db.commit()
    return goal

def clear_goal(session_id: str, chatbot_id: Optional[int]):
    """
    Cleans up any in-memory state for a goal. 
    With DB persistence, this is currently a no-op as the goal remains in the database 
    for persistence across reconnects.
    """
    logger.debug(f"[GOAL] Clearing in-memory state for session={session_id} chatbot={chatbot_id}")
