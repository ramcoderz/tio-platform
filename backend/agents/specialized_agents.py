from typing import Any
from backend.llm.ollama_client import ollama_client
from backend.config.settings import get_settings
import json
import re

settings = get_settings()

async def compare_documents(query: str, chunks: list) -> str:
    """Side-by-side comparison of multiple knowledge sources."""
    if len(chunks) < 2:
        return "Insufficient sources for comparative analysis. Please ingest more documents."
    
    prompt = f"""
    You are a Comparative Analysis Agent. Analyze the following information from different sources.
    Provide a side-by-side comparison.
    
    Query: {query}
    
    Sources:
    {json.dumps([{'doc': c.document, 'text': c.text} for c in chunks], indent=2)}
    
    Output Format:
    1. **Key Themes**: Shared topics across sources.
    2. **Point-by-Point Comparison**: A table-like breakdown of differences.
    3. **Contradictions**: Any conflicting information.
    4. **Recommendation**: Synthesis based on the most credible data.
    """
    return await ollama_client.generate(prompt, model=settings.ollama_model)

async def extract_structured_data(text: str) -> dict:
    """Extracts business metrics and entities into a structured JSON format."""
    prompt = f"""
    You are a Structured Extraction Agent. Extract key business metrics, entities, and dates from the following text.
    Return ONLY a valid JSON object with the following schema:
    {{
        "entities": ["list", "of", "names"],
        "metrics": {{ "name": "value" }},
        "dates": ["list", "of", "dates"],
        "confidence": 0.0-1.0
    }}
    
    Text: {text}
    """
    raw = await ollama_client.generate(prompt, model=settings.ollama_model)
    try:
        # Simple extraction logic
        match = re.search(r"(\{.*\})", raw, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        return {"error": "Failed to parse JSON", "raw": raw}
    except Exception as e:
        return {"error": str(e)}

async def orchestrate_tasks(text: str, session_id: str | None = None, db: Any = None) -> list[dict]:
    """Identifies and logs action items from conversational or document text."""
    prompt = f"""
    You are a Task Orchestration Agent. Identify all action items, owners, and deadlines from the text.
    Return ONLY a valid JSON list of objects:
    [
        {{ "task": "description", "owner": "name or 'Unknown'", "deadline": "date or 'Unspecified'" }}
    ]
    
    Text: {text}
    """
    raw = await ollama_client.generate(prompt, model=settings.ollama_model)
    try:
        match = re.search(r"(\[.*\])", raw, re.DOTALL)
        if match:
            tasks_data = json.loads(match.group(1))
            if db and session_id:
                from backend.models.entities import Task
                for t in tasks_data:
                    task_obj = Task(
                        session_id=session_id,
                        description=t.get("task", ""),
                        owner=t.get("owner"),
                        deadline=t.get("deadline")
                    )
                    db.add(task_obj)
                await db.commit()
            return tasks_data
        return []
    except Exception:
        return []
