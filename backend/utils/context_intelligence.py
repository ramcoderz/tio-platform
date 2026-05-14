"""
Context Intelligence — Synthesizes raw retrieval chunks into a structured understanding.
"""

import logging
import json
from typing import Any, Dict, List
from backend.llm.ollama_client import ollama_client
from backend.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class ContextSnapshot:
    def __init__(self, data: Dict[str, Any]):
        self.facts: List[str] = data.get("facts", [])
        self.entities: List[Dict[str, str]] = data.get("entities", [])
        self.workflows: List[str] = data.get("workflows", [])
        self.related_pages: List[str] = data.get("related_pages", [])
        self.relationships: List[str] = data.get("relationships", [])
        self.key_actions: List[str] = data.get("key_actions", [])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "facts": self.facts,
            "entities": self.entities,
            "workflows": self.workflows,
            "related_pages": self.related_pages,
            "relationships": self.relationships,
            "key_actions": self.key_actions
        }

    def __str__(self) -> str:
        res = ""
        if self.facts:
            res += "FACTS:\n- " + "\n- ".join(self.facts) + "\n"
        if self.workflows:
            res += "\nWORKFLOWS:\n- " + "\n- ".join(self.workflows) + "\n"
        if self.relationships:
            res += "\nRELATIONSHIPS:\n- " + "\n- ".join(self.relationships) + "\n"
        if self.key_actions:
            res += "\nAVAILABLE ACTIONS:\n- " + "\n- ".join(self.key_actions) + "\n"
        return res.strip()

async def synthesize_context(query: str, chunks: List[Any], goal: str | None = None) -> ContextSnapshot:
    """
    Analyzes raw chunks to build a structured ContextSnapshot.
    """
    if not chunks:
        return ContextSnapshot({})

    context_text = "\n\n".join([f"[Source: {c.document}]\n{c.text}" for c in chunks])
    
    prompt = f"""
    You are a Context Synthesis Engine. Analyze the following retrieved content for the user query: "{query}"
    Goal: {goal or "General inquiry"}

    Tasks:
    1. Extract core FACTS (specific, grounded, non-robotic).
    2. Identify active or related WORKFLOWS (e.g., "Applying for a visa", "Integrating the API").
    3. Map RELATIONSHIPS between entities mentioned (e.g., "Department A offers Course B").
    4. List KEY ACTIONS the user can take (e.g., "Click the Apply button", "Contact support at...").
    5. List RELATED PAGES mentioned in the text.

    FORMAT: Return a JSON object ONLY.
    {{
      "facts": ["..."],
      "entities": [{{ "name": "...", "type": "..." }}],
      "workflows": ["..."],
      "related_pages": ["..."],
      "relationships": ["..."],
      "key_actions": ["..."]
    }}

    CONTENT:
    {context_text[:12000]}
    """

    try:
        response = await ollama_client.generate(prompt, model=settings.ollama_model)
        
        # Simple extraction logic
        import re
        match = re.search(r"(\{.*\})", response, re.DOTALL)
        if match:
            json_str = match.group(1)
            data = json.loads(json_str)
            return ContextSnapshot(data)
        else:
            logger.warning("[CONTEXT INTEL] LLM returned no JSON structure.")
            return ContextSnapshot({"facts": [response[:500]]})
    except Exception as e:
        logger.error(f"[CONTEXT INTEL] Synthesis failed: {e}")
        return ContextSnapshot({"facts": ["Context synthesis unavailable due to a technical error."]})
