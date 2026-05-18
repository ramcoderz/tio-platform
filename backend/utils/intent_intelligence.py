import logging
from typing import Dict, List, Optional
from pydantic import BaseModel
from backend.rag.embeddings import embed
import numpy as np

logger = logging.getLogger(__name__)

class IntentScore(BaseModel):
    intent: str
    score: float

# Skill descriptions for semantic matching
SKILL_DESCRIPTIONS = {
    "tourism_planner": "plan a trip, create an itinerary, travel schedule, route optimization, sightseeing plan",
    "attraction_recommender": "recommend places to see, top attractions, must-see spots, popular destinations",
    "ride_optimizer": "wait times for rides, queue optimization, skip the line, theme park rides",
    "course_finder": "find educational programs, degrees, majors, courses, what to study",
    "admission_assistant": "how to apply, admission requirements, deadlines, enrollment process",
    "scholarship_helper": "financial aid, scholarships, grants, funding for students",
    "dept_navigator": "medical departments, which doctor to see, specialist recommendation, hospital routing",
    "appointment_guidance": "book a medical appointment, schedule a visit, hospital contact info",
    "insurance_assistant": "medical insurance coverage, billing, payment claims",
    "api_assistant": "how to use the API, code snippets, authentication, developer integration",
    "integration_helper": "system integration, webhooks, event flows, architectural setup",
    "sdk_guide": "install libraries, npm, pip, sdk initialization, package usage",
    "shopping_guide": "product comparison, buy items, pricing, shopping advice, retail catalog",
    "doc_summarizer": "summarize documents, key highlights, overview of content, tell me about this",
    "profile_lookup": "find faculty information, who is the professor, hod details, staff bio, dean profile, contact details",
    "credential_query": "work experience, professional background, qualifications, academic degrees, certifications, career history, resume details, cv content",
}

class IntentIntelligence:
    """
    Enhanced intent routing using semantic similarity.
    """
    def __init__(self):
        self.skill_embeddings: Dict[str, np.ndarray] = {}
        self._initialize_embeddings()

    def _initialize_embeddings(self):
        try:
            skills = list(SKILL_DESCRIPTIONS.keys())
            descriptions = list(SKILL_DESCRIPTIONS.values())
            vectors = embed(descriptions)
            for skill, vec in zip(skills, vectors):
                self.skill_embeddings[skill] = np.array(vec, dtype="float32")
            logger.info(f"[INTENT] Initialized embeddings for {len(skills)} skills.")
        except Exception as e:
            logger.error(f"[INTENT] Failed to initialize embeddings: {e}")

    def detect(self, query: str, eligible_skills: Optional[List[str]] = None) -> str:
        """
        Detects the best intent for a query using semantic similarity.
        """
        if not self.skill_embeddings:
            return "general_chat"

        try:
            q_vec = np.array(embed([query])[0], dtype="float32")
            scores: Dict[str, float] = {}

            skills_to_check = eligible_skills if eligible_skills else list(self.skill_embeddings.keys())
            
            for skill in skills_to_check:
                if skill in self.skill_embeddings:
                    # Cosine similarity
                    score = np.dot(q_vec, self.skill_embeddings[skill])
                    scores[skill] = float(score)

            if not scores:
                return "general_chat"

            best_skill = max(scores, key=scores.get)
            # Only return the skill if it's a reasonably strong match
            if scores[best_skill] > 0.4:
                return best_skill
            
            return "general_chat"
        except Exception as e:
            logger.error(f"[INTENT] Detection error: {e}")
            return "general_chat"

    def normalize_query(self, query: str) -> str:
        """
        Normalize synonyms to improve retrieval grounding.
        Focuses on tourism and common vague terms.
        """
        synonyms = {
            "location marks": "landmarks",
            "tourist spots": "attractions",
            "places to see": "destinations",
            "rides": "attractions",
            "spots": "destinations",
            "admission help": "how to apply",
            "wait times": "queue time",
            "where to go": "attractions",
            "must visit": "top attractions",
            "hod": "head of department",
            "dean": "faculty head",
            "principal": "institution head",
            "work history": "professional experience",
            "background": "qualifications and career",
        }
        q = query.lower()
        for old, new in synonyms.items():
            if old in q:
                q = q.replace(old, new)
        return q

intent_intelligence = IntentIntelligence()
