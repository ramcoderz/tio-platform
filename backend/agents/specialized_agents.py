from typing import Any
import json
import re
from backend.llm.ollama_client import ollama_client
from backend.config.settings import get_settings

settings = get_settings()

# ---------------------------------------------------------------------------
# SHARED PROMPT RULES — enforcing non-robotic, proactive behavior
# ---------------------------------------------------------------------------
PROACTIVE_RULES = """
========================================================
CRITICAL ENTITY RULES
========================================================
- NEVER generate placeholder-style entities such as [Cultural Institution], [Landmark], [Location], etc.
- ABSOLUTELY NO BRACKETS [ ] or template variables in your response.
- If specific names are missing from the context, admit it naturally: "The specific names were not identified in the indexed sources."
- NEVER fabricate names or landmarks.

========================================================
IDENTITY & TONE RULES
========================================================
- Never say "As an AI", "I'd be happy to help", or "As a [Role]".
- Speak with confidence. Make reasonable assumptions for vague queries.
- Be proactive: suggest logically related next steps or information.
"""


async def compare_documents(query: str, chunks: list) -> str:
    """Side-by-side comparison of multiple knowledge sources."""
    if len(chunks) < 2:
        return "I need more than one source to provide a side-by-side comparison. Please ingest additional documents."
    
    prompt = f"""
    Compare the following sources directly based on the query.
    {PROACTIVE_RULES}
    
    QUERY: {query}
    
    SOURCES:
    {json.dumps([{'doc': c.document, 'text': c.text} for c in chunks], indent=2)}
    
    OUTPUT FORMAT:
    1. **Direct Comparison**: A table or structured list showing differences.
    2. **Contradictions**: Any conflicting points between sources.
    3. **Recommendation**: Which source or path is best based on the data.
    """
    return await ollama_client.generate(prompt, model=settings.ollama_model)


async def tourism_planner_skill(place_name: str, website_context: str) -> str:
    """Specialized skill for creating a tourism plan based on reviews and site data."""
    from backend.agents.web_search_agent import search_web
    
    # 1. Search for reviews and community opinions
    search_query = f"{place_name} reviews visitor experiences tips reddit"
    review_chunks = await search_web(search_query, limit=5)
    reviews_text = "\n".join([f"- {c.text} (Source: {c.document})" for c in review_chunks])
    
    # 2. Generate the plan
    prompt = f"""
    Create an optimised travel itinerary and guide for: {place_name}
    {PROACTIVE_RULES}
    
    WEBSITE CONTEXT (Official details):
    {website_context}
    
    COMMUNITY FEEDBACK (Visitor reviews):
    {reviews_text if reviews_text else "No recent reviews found."}
    
    REQUIREMENTS:
    - Generate a logical daily itinerary based on the context.
    - Include "Pro Tips" (best times, hidden spots).
    - Include "Honest Expectations" (wait times, costs).
    - Synthesise official data with community feedback.
    
    STYLE: Enthusiastic, practical, and itinerary-focused.
    """
    return await ollama_client.generate(prompt, model=settings.ollama_model)


async def course_finder_skill(career_goal: str, website_context: str) -> str:
    """Education skill: match career goals to courses from context."""
    prompt = f"""Recommend specific programs and courses that lead to a career in: {career_goal}
    {PROACTIVE_RULES}

    CONTEXT:
    {website_context if website_context else "No specific course data available."}
    
    REQUIREMENTS:
    - Recommend at least 2-3 specific courses or programs from the context.
    - Explain the "Why" — how they align with the career goal.
    - List prerequisites, deadlines, and next steps immediately.
    - Suggest a logical sequence (Foundation -> Specialist).
    
    STYLE: Encouraging, student-focused, and direct.
    """
    return await ollama_client.generate(prompt, model=settings.ollama_model)


async def dept_navigator_skill(symptoms: str, website_context: str) -> str:
    """Medical skill: route users to the right department based on symptoms."""
    prompt = f"""Identify the most appropriate medical department for the following concern.
    {PROACTIVE_RULES}

    CONCERN: {symptoms}
    
    HOSPITAL DATA:
    {website_context if website_context else "No specific department data available."}
    
    REQUIREMENTS:
    - State the primary department recommendation immediately.
    - Provide contact details, hours, and location if available in the context.
    - If symptoms sound severe, lead with: "Please visit Emergency or call [number] immediately."
    - Synthesise routing logic — do not just list departments.
    
    STYLE: Professional, direct, and safety-aware.
    """
    return await ollama_client.generate(prompt, model=settings.ollama_model)


async def api_assistant_skill(integration_goal: str, website_context: str) -> str:
    """Developer skill: generate integration boilerplate from docs."""
    prompt = f"""Provide a complete integration guide for: {integration_goal}
    {PROACTIVE_RULES}

    DOCUMENTATION CONTEXT:
    {website_context if website_context else "No specific API docs available."}
    
    REQUIREMENTS:
    - Provide working code snippets immediately.
    - Detail authentication (Bearer, API Key) and base URLs.
    - List the specific endpoints and HTTP methods required.
    - Include a "Common Pitfalls" section.
    
    STYLE: Technical, concise, no marketing fluff.
    """
    return await ollama_client.generate(prompt, model=settings.ollama_model)


async def doc_summarizer_skill(website_context: str) -> str:
    """General skill: synthesize documents into key points."""
    prompt = f"""Distill this content into its 5 most critical insights.
    {PROACTIVE_RULES}

    CONTEXT:
    {website_context if website_context else "No documents available to summarize."}
    
    REQUIREMENTS:
    - Lead with the most important takeaway (TL;DR).
    - Group insights into logical themes.
    - Extract dates, deadlines, and entities into a separate list.
    - Keep it under 300 words.
    
    STYLE: Balanced, professional, and dense.
    """
    return await ollama_client.generate(prompt, model=settings.ollama_model)


# --- New Skills ---

async def ride_optimizer_skill(query: str, website_context: str) -> str:
    """Tourism: Optimize attraction visits."""
    prompt = f"""Provide an optimized visit sequence for these attractions/rides: {query}
    {PROACTIVE_RULES}
    
    CONTEXT: {website_context}
    
    REQUIREMENTS:
    - Order the visits to minimize wait times or walking overlap.
    - Suggest the best time of day for each.
    - Mention 'Fast Pass' or similar options if found.
    """
    return await ollama_client.generate(prompt, model=settings.ollama_model)

async def admission_assistant_skill(query: str, website_context: str) -> str:
    """Education: Application guidance."""
    prompt = f"""Provide step-by-step application guidance for: {query}
    {PROACTIVE_RULES}
    
    CONTEXT: {website_context}
    
    REQUIREMENTS:
    - List every required document found in the context.
    - State deadlines clearly (Bold them).
    - Provide the direct application link or contact if available.
    """
    return await ollama_client.generate(prompt, model=settings.ollama_model)

async def scholarship_helper_skill(query: str, website_context: str) -> str:
    """Education: Financial aid finder."""
    prompt = f"""Identify scholarship and financial aid opportunities for: {query}
    {PROACTIVE_RULES}
    
    CONTEXT: {website_context}
    
    REQUIREMENTS:
    - List specific scholarships with their eligibility criteria.
    - State the award amounts and deadlines.
    - Provide application steps.
    """
    return await ollama_client.generate(prompt, model=settings.ollama_model)

async def appointment_guidance_skill(query: str, website_context: str) -> str:
    """Medical: Booking guidance."""
    prompt = f"""Guide the user on how to book an appointment for: {query}
    {PROACTIVE_RULES}
    
    CONTEXT: {website_context}
    
    REQUIREMENTS:
    - Provide the central booking number or link.
    - Detail what the user needs to bring (ID, insurance, etc.).
    - List available time slots or office hours if mentioned.
    """
    return await ollama_client.generate(prompt, model=settings.ollama_model)

async def insurance_assistant_skill(query: str, website_context: str) -> str:
    """Medical: Coverage details."""
    prompt = f"""Clarify insurance coverage and billing for: {query}
    {PROACTIVE_RULES}
    
    CONTEXT: {website_context}
    
    REQUIREMENTS:
    - List accepted insurance providers found in the context.
    - Explain the billing process or co-pay requirements.
    - Be precise — do not guess if not in the context.
    """
    return await ollama_client.generate(prompt, model=settings.ollama_model)

async def integration_helper_skill(query: str, website_context: str) -> str:
    """Developer: Complex integration architecture."""
    prompt = f"""Design a system integration flow for: {query}
    {PROACTIVE_RULES}
    
    CONTEXT: {website_context}
    
    REQUIREMENTS:
    - Focus on webhooks, event flows, and error handling.
    - Provide a sequence diagram or logic flow (in Markdown).
    - Detail security best practices (retry logic, signature verification).
    """
    return await ollama_client.generate(prompt, model=settings.ollama_model)

async def sdk_guide_skill(query: str, website_context: str) -> str:
    """Developer: SDK setup."""
    prompt = f"""Provide a setup guide for the SDK: {query}
    {PROACTIVE_RULES}
    
    CONTEXT: {website_context}
    
    REQUIREMENTS:
    - Show installation commands (npm, pip, etc.).
    - Show the initialization code block.
    - Detail 3 common SDK functions and their parameters.
    """
    return await ollama_client.generate(prompt, model=settings.ollama_model)

async def shopping_guide_skill(query: str, website_context: str) -> str:
    """Ecommerce: Product recommendation and comparison."""
    prompt = f"""Compare the best product options for: {query}
    {PROACTIVE_RULES}
    
    CONTEXT: {website_context}
    
    REQUIREMENTS:
    - Use a Markdown table to compare 3-5 products.
    - Categories: Product Name, Price, Key Feature, Best For.
    - Recommend the best overall choice with a reason.
    """
    return await ollama_client.generate(prompt, model=settings.ollama_model)


# ---------------------------------------------------------------------------
# LEGACY / UTILITY AGENTS (to be kept for backend processing)
# ---------------------------------------------------------------------------

async def extract_structured_data(text: str) -> dict:
    """Extracts business metrics and entities into a structured JSON format."""
    prompt = f"""
    Extract key business metrics, entities, and dates from the following text.
    Return ONLY a valid JSON object.
    
    Schema:
    {{
        "entities": ["names"],
        "metrics": {{ "key": "val" }},
        "dates": ["YYYY-MM-DD"],
        "confidence": 0.0-1.0
    }}
    
    Text: {text}
    """
    raw = await ollama_client.generate(prompt, model=settings.ollama_model)
    try:
        match = re.search(r"(\{.*\})", raw, re.DOTALL)
        if match: return json.loads(match.group(1))
        return {}
    except: return {}


async def orchestrate_tasks(text: str, session_id: str | None = None, db: Any = None) -> list[dict]:
    """Identifies and logs action items from conversational or document text."""
    prompt = f"""
    Identify all action items, owners, and deadlines from the text.
    Return ONLY a valid JSON list of objects:
    [
        {{ "task": "description", "owner": "name", "deadline": "date" }}
    ]
    
    Text: {text}
    """
    raw = await ollama_client.generate(prompt, model=settings.ollama_model)
    try:
        match = re.search(r"(\[.*\])", raw, re.DOTALL)
        if not match: return []
        tasks_data = json.loads(match.group(1))
        if db and session_id:
            from backend.models.entities import Task
            for t in tasks_data:
                db.add(Task(session_id=session_id, description=t.get("task", ""), owner=t.get("owner"), deadline=t.get("deadline")))
            await db.commit()
        return tasks_data
    except: return []
