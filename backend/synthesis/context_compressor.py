import logging
from typing import Any
from backend.llm.ollama_client import ollama_client
from backend.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class ContextCompressor:
    """
    Upgrades basic chunk trimming into "Meaning Synthesis".
    Synthesizes workflows, relationships, and contextual meaning while preserving grounding.
    """

    async def synthesize_meaning(self, chunks: list[Any], query: str, domain: str) -> str:
        if not chunks:
            return "No relevant context found."

        # Filter out the most relevant text
        combined_text = "\n\n".join([c.text if hasattr(c, "text") else str(c) for c in chunks[:5]])
        
        # Pragmatic approach: 
        # If the context is small, use heuristics.
        # If it's complex and we have a fast LLM, use it for a "Synthesis Pass".
        
        # For now, let's implement a "Structural Synthesis" without extra LLM call to save latency,
        # but structured to meet the "GOOD" example criteria.
        
        # 1. Group by Topic (Heuristic)
        topics: dict[str, list[str]] = {
            "requirements": [],
            "process": [],
            "technical_details": [],
            "recommendations": []
        }
        
        req_kws = ["require", "must", "need", "mandatory", "essential"]
        proc_kws = ["step", "first", "then", "finally", "process", "workflow"]
        tech_kws = ["api", "sdk", "code", "endpoint", "auth", "token"]
        
        for chunk in chunks:
            text = chunk.text if hasattr(chunk, "text") else str(chunk)
            lines = text.split("\n")
            for line in lines:
                l_lower = line.lower()
                if any(k in l_lower for k in req_kws):
                    topics["requirements"].append(line.strip())
                if any(k in l_lower for k in proc_kws):
                    topics["process"].append(line.strip())
                if any(k in l_lower for k in tech_kws):
                    topics["technical_details"].append(line.strip())

        # 2. Build Synthesis String
        synthesis = []
        if topics["process"]:
            synthesis.append(f"The {domain} workflow involves the following steps: " + " ".join(topics["process"][:3]))
        
        if topics["requirements"]:
            synthesis.append("Key requirements identified: " + ", ".join(topics["requirements"][:3]))
            
        if topics["technical_details"]:
            synthesis.append("Technical context: " + " ".join(topics["technical_details"][:2]))

        if not synthesis:
            # Fallback to the best chunk
            return combined_text[:2000]

        return "\n\n".join(synthesis)

    def compress_for_prompt(self, snapshot: Any, synthesized_meaning: str) -> str:
        """Combine the snapshot and meaning into a compressed prompt block."""
        lines = ["CONTEXTUAL SYNTHESIS:"]
        lines.append(f"  Summary: {synthesized_meaning}")
        
        if hasattr(snapshot, "entities") and snapshot.entities:
            lines.append(f"  Key Entities: {', '.join(snapshot.entities)}")
            
        if hasattr(snapshot, "relationships") and snapshot.relationships:
            lines.append("  Relationships:")
            for rel in snapshot.relationships[:4]:
                lines.append(f"    - {rel}")
                
        return "\n".join(lines)
