from typing import Any

class ResponsePlanner:
    """
    Builds a structured response plan based on synthesized context and workflow state.
    """

    def plan(self, query: str, snapshot: Any, workflow_state: Any, domain: str) -> dict:
        plan = {
            "goal": workflow_state.active_goal or f"Address: {query[:50]}",
            "workflow": workflow_state.active_workflow,
            "stage": workflow_state.current_stage,
            "entities": snapshot.entities[:5],
            "key_facts": snapshot.facts[:5],
            "recommendations": [],
            "next_steps": workflow_state.pending_steps[:3],
            "structure": "Conversational with actionable synthesis"
        }

        # Dynamic structure selection
        if workflow_state.current_stage == "planning":
            plan["structure"] = "Step-by-step guidance with requirements"
        elif workflow_state.current_stage == "execution":
            plan["structure"] = "Direct technical/actionable steps"
        
        # Add proactive recommendations
        if domain == "developer":
            plan["recommendations"].append("Suggest reviewing authentication if not already done.")
        elif domain == "tourism":
            plan["recommendations"].append("Check if the user wants to see nearby dining options.")

        # Normalize Plan
        normalized_plan = {
            "goal": plan.get("goal", ""),
            "workflow": plan.get("workflow", ""),
            "response_structure": plan.get("structure", "conversational"),
            "steps": plan.get("next_steps", []),
            "reasoning": plan.get("reasoning", ""),
            "recommendations": plan.get("recommendations", [])
        }
        return normalized_plan

    def format_plan_for_prompt(self, plan: dict) -> str:
        lines = ["RESPONSE PLAN:"]
        lines.append(f"  Goal: {plan.get('goal', '')}")
        lines.append(f"  Current Workflow: {plan.get('workflow', '')}")
        lines.append(f"  Reference Entities: {', '.join(plan.get('entities', []))}")
        lines.append(f"  Structure: {plan.get('response_structure', 'conversational')}")
        
        recs = plan.get('recommendations', [])
        if recs:
            lines.append(f"  Proactive Focus: {'; '.join(recs)}")
            
        return "\n".join(lines)
