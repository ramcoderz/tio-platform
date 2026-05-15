import re
import logging
from typing import List, Set

logger = logging.getLogger(__name__)

# Noise words to filter out from entity extraction
_ENTITY_NOISE: Set[str] = {
    "The", "This", "That", "These", "Those", "Our", "Your", "We", "They",
    "He", "She", "It", "If", "In", "On", "At", "By", "For", "From",
    "With", "And", "Or", "But", "Not", "Are", "Is", "Was", "Were", "Be",
    "To", "Of", "As", "An", "A", "When", "Where", "How", "Why", "Which",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December", "Today", "Yesterday", "Tomorrow"
}

# Lazy-load spaCy
_nlp = None

def _get_nlp():
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load("en_core_web_sm")
        except Exception as e:
            logger.warning(f"[ENTITIES] Failed to load spaCy (en_core_web_sm): {e}")
            _nlp = False # Flag that we tried and failed
    return _nlp

def extract_entities(text: str) -> List[str]:
    """
    Extract proper nouns and named entities using spaCy NER (primary)
    with a robust heuristic fallback.
    """
    if not text: return []
    
    results = []
    seen = set()
    
    # 1. Primary: spaCy NER
    nlp = _get_nlp()
    if nlp:
        try:
            # Process in chunks if text is massive
            doc = nlp(text[:100000])
            for ent in doc.ents:
                # We care about Organizations, Persons, GPE (locations), Facilities, Products
                if ent.label_ in {"ORG", "PERSON", "GPE", "FAC", "PRODUCT", "WORK_OF_ART", "EVENT"}:
                    results.append(ent.text.strip())
        except Exception as e:
            logger.warning(f"[ENTITIES] spaCy extraction error: {e}")

    # 2. Fallback / Enrichment: Heuristics
    found = []
    # Title Case multi-word entities
    found += re.findall(r'\b[A-Z][a-z]+(?:\s+(?:of\s+|the\s+|and\s+|for\s+)?[A-Z][a-z]+)+\b', text)
    # All-caps acronyms (2–6 chars)
    found += re.findall(r'\b[A-Z]{2,6}\b', text)
    # Quoted names
    found += re.findall(r'"([A-Z][^"]{2,40})"', text)
    # Titles followed by Name
    found += re.findall(r'\b(?:Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.|Professor|Officer)\s+[A-Z][a-z]+\b', text)

    results += found

    # 3. Clean and Filter
    final_results = []
    for e in results:
        e = e.strip()
        if not e or e in seen or e in _ENTITY_NOISE or len(e) < 3:
            continue
        
        # Basic validation: must contain at least one alpha char
        if not any(c.isalpha() for c in e):
            continue
            
        # Filter out obvious noisy starts like "The "
        if e.split()[0] in _ENTITY_NOISE and len(e.split()) == 1:
            continue
            
        final_results.append(e)
        seen.add(e)

    return final_results[:50]

def extract_entities_batch(texts: List[str]) -> List[List[str]]:
    """
    Extract entities for a batch of strings efficiently using nlp.pipe.
    """
    if not texts: return []
    
    nlp = _get_nlp()
    if not nlp:
        # Fallback to individual heuristic extraction if spaCy is missing
        return [extract_entities(t) for t in texts]

    results = []
    try:
        # Using nlp.pipe for efficiency
        for doc in nlp.pipe(texts, batch_size=16):
            doc_entities = []
            seen = set()
            
            # NER matches
            for ent in doc.ents:
                if ent.label_ in {"ORG", "PERSON", "GPE", "FAC", "PRODUCT", "WORK_OF_ART", "EVENT"}:
                    text = ent.text.strip()
                    if text not in seen and text not in _ENTITY_NOISE and len(text) >= 3:
                        doc_entities.append(text)
                        seen.add(text)
            
            # Plus heuristics (simplified for speed in batch)
            found = re.findall(r'\b[A-Z]{2,6}\b', doc.text) # Acronyms
            for e in found:
                if e not in seen and e not in _ENTITY_NOISE:
                    doc_entities.append(e)
                    seen.add(e)
            
            results.append(doc_entities[:30])
    except Exception as e:
        logger.warning(f"[ENTITIES] Batch extraction error: {e}")
        return [extract_entities(t) for t in texts]

    return results

def get_query_entities(query: str) -> List[str]:
    """Specific entity extraction for short user queries."""
    results = []
    
    # 1. Primary: spaCy NER
    nlp = _get_nlp()
    if nlp:
        try:
            doc = nlp(query)
            for ent in doc.ents:
                if ent.label_ in {"PERSON", "ORG", "FAC", "GPE", "PRODUCT", "WORK_OF_ART"}:
                    results.append(ent.text.strip())
        except Exception as e:
            logger.warning(f"[ENTITIES] query spaCy extraction error: {e}")

    # 2. Fallback / Enrichment: Heuristics
    found = re.findall(r'\b[A-Z][a-z]+\b', query)
    found += re.findall(r'\b[A-Z]{2,6}\b', query)
    
    for f in found:
        if f not in _ENTITY_NOISE and len(f) > 2 and f not in results:
            results.append(f)
            
    return results
