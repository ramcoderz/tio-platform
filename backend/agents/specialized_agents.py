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

async def tourism_planner_skill(place_name: str, website_context: str) -> str:
    """Specialized skill for creating a tourism plan based on reviews and site data."""
    from backend.agents.web_search_agent import search_web
    
    # 1. Search for reviews and community opinions
    search_query = f"{place_name} reviews visitor experiences tips reddit"
    review_chunks = await search_web(search_query, limit=5)
    reviews_text = "\n".join([f"- {c.text} (Source: {c.document})" for c in review_chunks])
    
    # 2. Generate the plan
    prompt = f"""
    You are a Premium Tourism Planner. Your goal is to create a detailed, high-value travel plan for: {place_name}
    
    WEBSITE CONTEXT (Official details):
    {website_context}
    
    VISITOR REVIEWS & COMMUNITY FEEDBACK:
    {reviews_text if reviews_text else "No recent reviews found. Plan based on official details."}
    
    PLANNING REQUIREMENTS:
    - Create a logical itinerary (1-day or multi-day as appropriate).
    - Include "Pro Tips" based on visitor feedback (e.g., best times to visit, hidden gems).
    - Add a "Honest Expectations" section based on reviews (e.g., "Lines can be long on weekends").
    - Highlight specific attractions mentioned in both official data and reviews.
    
    STYLE: Creative, welcoming, and recommendation-focused.
    """
    return await ollama_client.generate(prompt, model=settings.ollama_model)


async def course_finder_skill(career_goal: str, website_context: str) -> str:
    """Education skill: match career goals to courses from context."""
    prompt = f"""You are an Academic Advisor. A student has a career goal and needs course recommendations.

CAREER GOAL: {career_goal}

AVAILABLE COURSE/PROGRAM INFORMATION:
{website_context if website_context else "No specific course data available. Provide general guidance."}

REQUIREMENTS:
- Recommend the most relevant courses/programs based on the goal.
- Explain how each recommendation aligns with the career path.
- Include prerequisites or admission requirements if mentioned.
- Suggest a logical study sequence if multiple courses apply.
- Be encouraging and student-friendly.

Format the response with clear headers and bullet points."""
    return await ollama_client.generate(prompt, model=settings.ollama_model)


async def dept_navigator_skill(symptoms: str, website_context: str) -> str:
    """Medical skill: route users to the right department based on symptoms."""
    prompt = f"""You are a Medical Reception Assistant. Help a patient find the right department.

PATIENT CONCERN: {symptoms}

HOSPITAL/CLINIC DEPARTMENTS AND SERVICES:
{website_context if website_context else "No specific department data available."}

REQUIREMENTS:
- Suggest the most relevant department(s) based on the concern.
- Explain briefly why that department is appropriate.
- Include any mentioned contact details, hours, or location.
- If the concern sounds urgent, recommend visiting the Emergency department.
- Add a disclaimer: "This is for guidance only. Please consult with medical staff."

Format the response clearly with department names highlighted."""
    return await ollama_client.generate(prompt, model=settings.ollama_model)


async def api_assistant_skill(integration_goal: str, website_context: str) -> str:
    """Developer skill: generate integration boilerplate from docs."""
    prompt = f"""You are a Developer Relations Engineer. Help a developer integrate with this platform.

INTEGRATION GOAL: {integration_goal}

API/SDK DOCUMENTATION:
{website_context if website_context else "No specific API docs available."}

REQUIREMENTS:
- Provide a step-by-step integration guide.
- Include working code snippets (Python, JavaScript, or cURL).
- Highlight authentication requirements.
- List relevant endpoints with HTTP methods.
- Include error handling best practices.
- Be concise and technical — no fluff.

Format with code blocks and clear section headers."""
    return await ollama_client.generate(prompt, model=settings.ollama_model)


async def doc_summarizer_skill(website_context: str) -> str:
    """General skill: synthesize documents into key points."""
    prompt = f"""You are a Knowledge Synthesizer. Distill the following information into a concise, actionable summary.

DOCUMENTS AND CONTEXT:
{website_context if website_context else "No documents available to summarize."}

REQUIREMENTS:
- Extract the top 5-7 key insights.
- Group findings by theme if applicable.
- Highlight any important dates, deadlines, or action items.
- Note any gaps or missing information.
- Keep the summary under 400 words.

Format with numbered key points and a brief conclusion."""
    return await ollama_client.generate(prompt, model=settings.ollama_model)
