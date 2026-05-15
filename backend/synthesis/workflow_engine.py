from dataclasses import dataclass, field
from typing import Any

@dataclass
class WorkflowState:
    active_goal: str | None = None
    active_workflow: str | None = None
    current_stage: str = "browsing"
    completed_steps: list[str] = field(default_factory=list)
    pending_steps: list[str] = field(default_factory=list)
    last_action: str | None = None

class WorkflowEngine:
    """
    Manages conversational continuity and goal persistence.
    Tracks what the user is trying to achieve and where they are in the process.
    """

    def synthesize_workflow(self, query: str, intent: str, current_goal: Any, history: list[dict]) -> WorkflowState:
        state = WorkflowState()
        
        # 1. Inherit from current goal if exists
        if current_goal:
            state.active_goal = getattr(current_goal, "current_goal", None)
            state.active_workflow = getattr(current_goal, "active_workflow", None)
            state.current_stage = getattr(current_goal, "workflow_stage", "browsing")
            
            # Extract state from JSON if available
            state_json = getattr(current_goal, "state_json", {}) or {}
            state.completed_steps = state_json.get("completed_steps", [])
            state.pending_steps = state_json.get("pending_steps", [])

        # 2. Update based on new intent and query
        if not state.active_workflow and intent != "general_chat":
            state.active_workflow = intent
        
        # 3. Detect stage transitions
        # Simple heuristic: if user asks "how", "process", "steps" -> planning
        # if user asks "book", "apply", "submit" -> execution/booking
        q_lower = query.lower()
        if any(kw in q_lower for kw in ["how", "process", "steps", "plan", "start"]):
            state.current_stage = "planning"
        elif any(kw in q_lower for kw in ["book", "apply", "submit", "register", "buy"]):
            state.current_stage = "execution"
            
        # 4. Proactive guidance based on stage
        # (This will be used by the prompt orchestrator to suggest next steps)
        
        return state

    def get_proactive_recommendations(self, domain: str, state: WorkflowState) -> list[str]:
        """Generate proactive recommendations based on domain and workflow state."""
        recommendations = []
        
        if domain == "developer":
            if state.current_stage == "browsing":
                recommendations.append("Would you like to see the authentication setup?")
            elif state.current_stage == "planning":
                recommendations.append("Should we look at the SDK installation guide?")
        
        elif domain == "tourism":
            if state.current_stage == "browsing":
                recommendations.append("Shall I suggest some nearby attractions?")
            elif state.current_stage == "planning":
                recommendations.append("Would you like me to help optimize your travel route?")

        return recommendations
