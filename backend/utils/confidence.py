"""
Context Confidence System — determines how confident TiO is at each layer:

  - retrieval_confidence: how many grounded chunks were found
  - domain_confidence: how certain we are about the site domain
  - intent_confidence: how certain we are about what the user wants

Logic:
  - HIGH confidence → infer and answer directly (no clarifying questions)
  - MEDIUM confidence → answer with hedging
  - LOW confidence → gracefully fallback, surface related topics
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceReport:
    retrieval_confidence: float    # 0.0 – 1.0
    domain_confidence: float       # 0.0 – 1.0
    intent_confidence: float       # 0.0 – 1.0
    overall: float                 # weighted average
    should_infer: bool             # True → answer directly; False → fallback / hedge
    should_ask: bool               # True → ask a targeted clarifying question
    fallback_reason: str           # empty string if no fallback needed


def compute_retrieval_confidence(chunks: list, query: str) -> float:
    """
    Score the retrieval quality based on:
      - Number of chunks returned
      - Average chunk score
      - Whether any chunks have high individual scores
    """
    if not chunks:
        return 0.0

    n = len(chunks)
    avg_score = sum(getattr(c, "score", 0.5) for c in chunks) / n
    top_score = max(getattr(c, "score", 0.5) for c in chunks)

    # Normalise: 5+ chunks with avg score > 0.3 = high confidence
    chunk_factor = min(n / 5.0, 1.0)          # 0–1 based on chunk count
    score_factor = min(avg_score / 0.5, 1.0)  # 0–1 based on avg score
    top_factor = min(top_score / 0.4, 1.0)    # 0–1 based on top score

    confidence = (chunk_factor * 0.4) + (score_factor * 0.3) + (top_factor * 0.3)
    return round(min(confidence, 1.0), 3)


def compute_domain_confidence(domain: str, detected_scores: list | None = None) -> float:
    """
    Score domain confidence based on:
      - Whether domain is non-general
      - The gap between top-1 and top-2 domain scores
    """
    if not domain or domain == "general":
        return 0.3  # general = uncertain

    if detected_scores and len(detected_scores) >= 2:
        sorted_scores = sorted(detected_scores, key=lambda x: x.score, reverse=True)
        top = sorted_scores[0].score
        second = sorted_scores[1].score
        if top == 0:
            return 0.3
        gap = (top - second) / (top + 1e-9)
        confidence = 0.5 + (gap * 0.5)  # gap 0→50%, gap 1→100%
        return round(min(confidence, 1.0), 3)

    return 0.7  # domain set explicitly → reasonable confidence


def compute_intent_confidence(intent: str, keyword_score: int, semantic_score: float) -> float:
    """
    Score intent confidence based on:
      - Whether intent is non-generic
      - Keyword hit count
      - Semantic similarity score
    """
    if not intent or intent == "general_chat":
        return 0.3

    keyword_factor = min(keyword_score / 3.0, 1.0) * 0.4
    semantic_factor = min(semantic_score / 0.6, 1.0) * 0.6

    confidence = keyword_factor + semantic_factor
    return round(min(confidence, 1.0), 3)


def build_confidence_report(
    chunks: list,
    query: str,
    domain: str,
    intent: str,
    keyword_score: int = 0,
    semantic_score: float = 0.5,
    detected_scores: list | None = None,
) -> ConfidenceReport:
    """
    Build a unified confidence report for a single query turn.
    """
    r_conf = compute_retrieval_confidence(chunks, query)
    d_conf = compute_domain_confidence(domain, detected_scores)
    i_conf = compute_intent_confidence(intent, keyword_score, semantic_score)

    # Weighted overall (retrieval matters most)
    overall = (r_conf * 0.5) + (d_conf * 0.25) + (i_conf * 0.25)
    overall = round(overall, 3)

    # Decision thresholds
    should_infer = overall >= 0.45
    should_ask = overall < 0.25 and len(query.split()) < 5

    fallback_reason = ""
    if r_conf < 0.2:
        fallback_reason = "Insufficient grounding in indexed content"
    elif d_conf < 0.3:
        fallback_reason = "Domain of the site is unclear"
    elif i_conf < 0.3:
        fallback_reason = "User intent is ambiguous"

    report = ConfidenceReport(
        retrieval_confidence=r_conf,
        domain_confidence=d_conf,
        intent_confidence=i_conf,
        overall=overall,
        should_infer=should_infer,
        should_ask=should_ask,
        fallback_reason=fallback_reason,
    )

    logger.debug(
        f"[CONFIDENCE] retrieval={r_conf} domain={d_conf} intent={i_conf} "
        f"overall={overall} infer={should_infer} ask={should_ask}"
    )
    return report


def build_fallback_message(report: ConfidenceReport, domain: str) -> str:
    """Return a graceful fallback message when confidence is too low."""
    domain_hints = {
        "tourism": "attractions, itineraries, hotels, or local activities",
        "education": "courses, admissions, scholarships, or campus information",
        "medical": "departments, appointments, specialists, or healthcare services",
        "developer": "API authentication, endpoints, SDKs, or integrations",
        "ecommerce": "products, pricing, orders, or return policies",
        "general": "the topics covered on this site",
    }
    hint = domain_hints.get(domain, "the topics covered on this site")
    reason = report.fallback_reason or "the indexed content doesn't clearly cover this topic"

    return (
        f"I wasn't able to find specific information on that — {reason}. "
        f"I can help you with {hint}. What would you like to know?"
    )
