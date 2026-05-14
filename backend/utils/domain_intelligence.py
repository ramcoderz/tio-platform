import logging
import numpy as np
from typing import Dict, List, Optional
from pydantic import BaseModel
from backend.rag.embeddings import embed

logger = logging.getLogger(__name__)

class DomainScore(BaseModel):
    domain: str
    score: float
    indicators: List[str]

DOMAIN_INDICATORS = {
    "education": [
        "admissions", "faculty", "courses", "departments", "semester", "placements",
        "university", "college", "campus", "scholarship", "curriculum", "syllabus",
        "student", "academic", "degree", "graduate", "undergraduate", "alumni",
        "registrar", "dean", "provost", "tuition", "transcript"
    ],
    "medical": [
        "appointments", "doctors", "insurance", "departments", "patient care",
        "hospital", "clinic", "symptom", "treatment", "diagnosis", "specialist",
        "consultation", "healthcare", "medical", "pharmacy", "wellness", "radiology",
        "cardiology", "oncology", "pediatrics", "surgery", "nurse"
    ],
    "tourism": [
        "attractions", "itinerary", "destinations", "rides", "events", "hotels",
        "travel", "tour", "sightseeing", "vacation", "booking", "resort",
        "guide", "heritage", "adventure", "explore", "museum", "gallery",
        "landmark", "monument", "excursion"
    ],
    "developer": [
        "api", "sdk", "integrations", "authentication", "webhooks", "documentation",
        "endpoint", "library", "developer", "backend", "frontend", "git",
        "deployment", "hosting", "cloud", "software", "saas", "bearer", "oauth",
        "json", "rest", "graphql", "npm", "pip", "webhook", "sandbox", "callback"
    ],
    "ecommerce": [
        "products", "pricing", "catalog", "orders", "shipping", "cart",
        "checkout", "payment", "inventory", "sales", "discount", "offer",
        "customer", "retail", "store", "purchase", "refund", "sku", "wishlist",
        "coupons", "marketplace"
    ],
}

DOMAIN_DESCRIPTIONS = {
    "education": "Educational institution, university, college, courses, admissions, faculty, and student life.",
    "medical": "Medical services, hospital, clinic, doctors, healthcare, patient care, and treatments.",
    "tourism": "Travel, tourism, attractions, itineraries, hotels, and vacation planning.",
    "developer": "Software development, API documentation, SDKs, technical integrations, and tools.",
    "ecommerce": "Online shopping, products, retail catalog, pricing, and orders.",
}

class DomainDetector:
    """
    Lightweight domain intelligence using keyword indicators and metadata scoring.
    """

    def __init__(self):
        self.indicators = DOMAIN_INDICATORS
        self.domain_embeddings: Dict[str, np.ndarray] = {}
        self._initialize_embeddings()

    def _initialize_embeddings(self):
        try:
            domains = list(DOMAIN_DESCRIPTIONS.keys())
            desc = list(DOMAIN_DESCRIPTIONS.values())
            vectors = embed(desc)
            for d, v in zip(domains, vectors):
                self.domain_embeddings[d] = np.array(v, dtype="float32")
        except Exception as e:
            logger.error(f"[DOMAIN] Embedding init failed: {e}")

    def detect(self, text: str, metadata: Optional[Dict] = None) -> str:
        """
        Detects the domain of a given text/content.
        Returns the domain string or 'general'.
        Uses a strict confidence threshold.
        """
        if not text:
            return "general"

        scores = self.get_scores(text, metadata)
        if not scores:
            return "general"

        # Sort by score descending
        sorted_scores = sorted(scores, key=lambda x: x.score, reverse=True)
        top = sorted_scores[0]
        
        # Confidence Threshold: 
        # 1. Top score must be > 3.0 (strong indicator match)
        # 2. OR Semantic match must be very strong (> 0.6 boost equivalent)
        # 3. OR Gap between top and second must be significant
        second_score = sorted_scores[1].score if len(sorted_scores) > 1 else 0.0
        
        is_confident = (top.score >= 3.0) or (top.score > 1.5 and (top.score - second_score) > 1.0)
        
        if is_confident:
            return top.domain

        return "general"

    def get_scores(self, text: str, metadata: Optional[Dict] = None) -> List[DomainScore]:
        import re
        text_lower = text.lower()
        results = []

        # 1. Semantic Signal (only if text is long enough)
        semantic_scores = {}
        if len(text.split()) > 20 and self.domain_embeddings:
            try:
                q_vec = np.array(embed([text[:2000]])[0], dtype="float32")
                for d, v in self.domain_embeddings.items():
                    semantic_scores[d] = float(np.dot(q_vec, v))
            except: pass

        for domain, keywords in self.indicators.items():
            score = 0.0
            matched_indicators = []

            # Keyword matching
            for kw in keywords:
                if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
                    score += 1.0
                    matched_indicators.append(kw)

            # Semantic boost
            s_score = semantic_scores.get(domain, 0.0)
            if s_score > 0.4:
                score += (s_score * 10)
                matched_indicators.append("semantic_match")

            # Metadata weighting (if available)
            if metadata:
                title = metadata.get("title", "").lower()
                url = metadata.get("url", "").lower()
                
                for kw in keywords:
                    if kw in title:
                        score += 3.0
                        matched_indicators.append(f"title:{kw}")
                    if kw in url:
                        score += 2.0
                        matched_indicators.append(f"url:{kw}")

            results.append(DomainScore(
                domain=domain,
                score=score,
                indicators=list(set(matched_indicators))
            ))

        return results

domain_detector = DomainDetector()
