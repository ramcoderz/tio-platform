"""
Query Expansion — expands short user queries into richer retrieval queries.

Strategy:
  1. Domain-specific synonym/concept expansion
  2. Query normalization (vague -> concrete)
  3. Returns an expanded query string for retrieval ONLY (not shown to user)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain expansion vocabularies
# ---------------------------------------------------------------------------

DOMAIN_EXPANSIONS: dict[str, dict[str, list[str]]] = {
    "tourism": {
        "rides": ["attractions", "thrill rides", "water rides", "family rides", "roller coasters"],
        "food": ["dining", "restaurants", "cafes", "food stalls", "cuisine"],
        "best": ["top", "popular", "must-see", "recommended", "featured"],
        "visit": ["attractions", "destinations", "places to see", "sightseeing"],
        "plan": ["itinerary", "schedule", "route", "day plan"],
        "hotel": ["accommodation", "lodging", "resort", "stay"],
        "things to do": ["attractions", "activities", "experiences", "events"],
        "cheap": ["budget", "affordable", "low cost", "discount"],
    },
    "education": {
        "apply": ["admission", "enroll", "application process", "registration"],
        "course": ["program", "degree", "major", "curriculum"],
        "fees": ["tuition", "cost", "payment", "financial", "scholarship"],
        "when": ["deadline", "date", "schedule", "semester", "term"],
        "job": ["placement", "career", "employment", "internship"],
    },
    "medical": {
        "pain": ["symptom", "condition", "specialist", "treatment", "consultation"],
        "book": ["appointment", "schedule", "visit", "consultation booking"],
        "insurance": ["coverage", "billing", "claims", "payment", "plan"],
        "doctor": ["specialist", "consultant", "physician", "department"],
        "emergency": ["urgent care", "ER", "emergency department", "critical"],
    },
    "developer": {
        "connect": ["authenticate", "API key", "token", "endpoint", "integration"],
        "error": ["exception", "status code", "debugging", "troubleshoot", "logs"],
        "install": ["npm install", "pip install", "setup", "initialization", "library"],
        "api": ["endpoint", "REST", "HTTP", "request", "response", "authentication"],
        "webhook": ["event", "callback", "notification", "trigger", "payload"],
    },
    "ecommerce": {
        "buy": ["purchase", "order", "checkout", "add to cart"],
        "price": ["cost", "pricing", "discount", "offer", "sale"],
        "return": ["refund", "exchange", "return policy", "money back"],
        "shipping": ["delivery", "dispatch", "tracking", "logistics"],
    },
    "general": {
        "what is": ["overview", "description", "about", "summary"],
        "how to": ["guide", "steps", "process", "instructions"],
        "help": ["support", "assistance", "guidance", "information"],
    },
}

# Cross-domain normalizations
UNIVERSAL_SYNONYMS: dict[str, str] = {
    "location marks": "landmarks",
    "tourist spots": "attractions",
    "places to see": "destinations",
    "where to go": "attractions",
    "must visit": "top attractions",
    "wait times": "queue time",
    "admission help": "how to apply",
    "spots": "destinations",
    "hrs": "hours",
    "info": "information",
    "asap": "urgent",
}


# ---------------------------------------------------------------------------
# Main expander
# ---------------------------------------------------------------------------

def expand_query(query: str, domain: Optional[str] = None) -> str:
    """
    Expand a user query for better retrieval coverage.
    Returns an enriched query string (for retrieval only, not shown to user).
    """
    q = query.lower().strip()

    # 1. Apply universal synonyms
    for old, new in UNIVERSAL_SYNONYMS.items():
        if old in q:
            q = q.replace(old, new)

    # 2. Domain-specific expansion
    extra_terms: list[str] = []
    expansions = DOMAIN_EXPANSIONS.get(domain or "general", {})

    for trigger, synonyms in expansions.items():
        if trigger in q:
            # Add top 3 synonyms as expansion context
            extra_terms.extend(synonyms[:3])

    # Also check general expansions
    for trigger, synonyms in DOMAIN_EXPANSIONS["general"].items():
        if trigger in q:
            extra_terms.extend(synonyms[:2])

    # 3. Build final expanded query
    if extra_terms:
        # De-duplicate and append expansion terms
        unique_extras = list(dict.fromkeys(t for t in extra_terms if t.lower() not in q))
        if unique_extras:
            expanded = q + " " + " ".join(unique_extras[:6])
            logger.debug(f"[EXPAND] '{query}' -> '{expanded}'")
            return expanded

    return q

