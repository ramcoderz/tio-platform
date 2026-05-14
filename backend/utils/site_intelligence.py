"""
Website Understanding Layer — analyzes crawled content to build a site profile.
"""

import logging
import re
from typing import Any, Dict, List
from collections import Counter
import datetime
from backend.llm.ollama_client import ollama_client
from backend.config.settings import get_settings
from backend.utils.entities import extract_entities

logger = logging.getLogger(__name__)
settings = get_settings()

async def build_site_profile(all_text: str, domain: str, site_url: str) -> Dict[str, Any]:
    """
    Generate a persistent intelligence profile for a website.
    Analyzes all_text (combined crawled content) to extract core metadata.
    """
    logger.info(f"[SITE INTEL] Building profile for {site_url} (domain={domain})")
    
    # 1. High-level summary (via LLM)
    # We use a truncated version of all_text if it's too large
    context_for_llm = all_text[:8000] 
    
    summary_prompt = f"""
    Analyze the following website content for {site_url} ({domain} domain).
    Provide a concise (2-3 sentence) summary of what this organization is and what they offer.
    Format your response as a direct summary, no preamble.

    CONTENT:
    {context_for_llm}
    """
    
    try:
        summary = await ollama_client.generate(summary_prompt, model=settings.ollama_model)
    except Exception as e:
        logger.warning(f"[SITE INTEL] Summary generation failed: {e}")
        summary = f"A website focused on {domain} located at {site_url}."

    # 2. Extract Top Entities
    entities = extract_entities(all_text)
    # Keep top 15 most frequent/relevant entities
    top_entities = [e for e, _ in Counter(entities).most_common(15)]

    # 3. Detect Key Services
    services = _detect_services(all_text, domain)

    # 4. Detect Workflows
    workflows = _detect_workflows(all_text, domain)

    # 5. Detect Relationships (Lightweight Mapping)
    relationships = _detect_relationships(all_text, domain)

    profile = {
        "url": site_url,
        "domain": domain,
        "site_summary": summary.strip(),
        "top_entities": top_entities,
        "key_services": services,
        "workflows": workflows,
        "relationships": relationships,
        "ingested_at": str(datetime.datetime.utcnow()),
    }
    
    logger.info(f"[SITE INTEL] Profile complete: {len(top_entities)} entities, {len(services)} services, {len(relationships)} relationships.")
    return profile

def _detect_relationships(text: str, domain: str) -> List[str]:
    """Extract lightweight relationship mappings based on domain context."""
    text_lower = text.lower()
    rels = []
    
    patterns = {
        "tourism": [
            r"(\w+)\s+is\s+located\s+in\s+the\s+(\w+)\s+zone",
            r"near\s+the\s+(\w+)\s+you\s+can\s+find\s+(\w+)",
        ],
        "education": [
            r"(\w+)\s+department\s+offers\s+(\w+)",
            r"faculty\s+of\s+(\w+)\s+includes\s+(\w+)",
        ],
        "developer": [
            r"(\w+)\s+requires\s+(\w+)\s+authentication",
            r"use\s+the\s+(\w+)\s+sdk\s+to\s+(\w+)",
        ],
        "medical": [
            r"(\w+)\s+department\s+specializes\s+in\s+(\w+)",
            r"consult\s+a\s+(\w+)\s+for\s+(\w+)",
        ]
    }
    
    domain_patterns = patterns.get(domain, [])
    for p in domain_patterns:
        matches = re.findall(p, text_lower)
        for m in matches:
            if isinstance(m, tuple):
                rels.append(f"{m[0].title()} -> {m[1].title()}")
            else:
                rels.append(str(m).title())
                
    return list(set(rels))[:10]


def _detect_services(text: str, domain: str) -> List[str]:
    """Identify key services based on domain patterns."""
    text_lower = text.lower()
    services = []
    
    # Domain specific service keywords
    indicators = {
        "tourism": ["tour", "hotel", "ride", "attraction", "itinerary", "booking", "package"],
        "education": ["admission", "course", "degree", "scholarship", "faculty", "program"],
        "medical": ["appointment", "specialist", "surgery", "clinic", "treatment", "therapy"],
        "developer": ["api", "sdk", "documentation", "integration", "webhook", "support"],
        "ecommerce": ["product", "shipping", "return", "pricing", "catalog"],
    }
    
    relevant = indicators.get(domain, [])
    # Find sentences containing these keywords that look like service headers
    for item in relevant:
        # Look for headers or bullet points like "Our [Service]" or "[Service] Offerings"
        pattern = rf"(?:our|available|key|main)\s+({item}[a-z]*\s+[a-z]+)"
        matches = re.findall(pattern, text_lower)
        if matches:
            services.extend([m.title() for m in matches])
            
    return list(set(services))[:8]

def _detect_workflows(text: str, domain: str) -> List[str]:
    """Identify common user workflows."""
    workflows = []
    # Common workflow patterns: "How to X", "Step 1: Y", "Apply for Z"
    patterns = [
        r"how to ([^.?!,]+)",
        r"step \d:? ([^.?!,]+)",
        r"apply for ([^.?!,]+)",
        r"book a ([^.?!,]+)",
        r"register for ([^.?!,]+)",
    ]
    
    for p in patterns:
        matches = re.findall(p, text.lower())
        if matches:
            workflows.extend([f"How to {m.strip()}" for m in matches if len(m.strip().split()) < 6])
            
    return list(set(workflows))[:5]

def get_site_context_string(profile: Dict[str, Any]) -> str:
    """Format the site profile for inclusion in the LLM system prompt."""
    if not profile: return ""
    
    ctx = f"ORGANIZATION CONTEXT:\n"
    ctx += f"- Summary: {profile.get('site_summary')}\n"
    if profile.get("top_entities"):
        ctx += f"- Key Entities: {', '.join(profile.get('top_entities'))}\n"
    if profile.get("key_services"):
        ctx += f"- Key Services: {', '.join(profile.get('key_services'))}\n"
    if profile.get("workflows"):
        ctx += f"- Available Workflows: {', '.join(profile.get('workflows'))}\n"
    return ctx
