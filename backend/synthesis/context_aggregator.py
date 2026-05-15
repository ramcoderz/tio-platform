import re
from dataclasses import dataclass, field
from typing import Any

@dataclass
class ContextSnapshot:
    facts: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    workflows: list[str] = field(default_factory=list)
    relationships: list[str] = field(default_factory=list)
    important_actions: list[str] = field(default_factory=list)
    related_pages: list[str] = field(default_factory=list)

class ContextAggregator:
    """
    Transforms isolated retrieval chunks into synthesized contextual understanding.
    Groups related entities, detects workflows, and identifies relationships.
    """

    def aggregate(self, chunks: list[Any], query: str, site_profile: dict) -> ContextSnapshot:
        snapshot = ContextSnapshot()
        
        if not chunks:
            return snapshot

        # 1. Extract and Deduplicate Entities
        seen_entities = set()
        for chunk in chunks:
            text = chunk.text if hasattr(chunk, "text") else str(chunk)
            # Find capitalized proper nouns (basic heuristic)
            found = re.findall(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*\b", text)
            for ent in found:
                if len(ent) > 3 and ent.lower() not in ["the", "this", "that"]:
                    seen_entities.add(ent)
        
        snapshot.entities = sorted(list(seen_entities))[:15]

        # 2. Identify Related Pages (Source Attribution)
        pages = set()
        for chunk in chunks:
            doc = getattr(chunk, "document", "Unknown")
            if doc and doc != "Unknown":
                pages.add(doc)
        snapshot.related_pages = list(pages)

        # 3. Detect Workflows (Keyword + Domain context)
        # We look for action-oriented sentences or lists
        workflow_keywords = ["step", "first", "then", "finally", "how to", "process", "guide", "setup", "integrate"]
        for chunk in chunks:
            text = chunk.text if hasattr(chunk, "text") else str(chunk)
            sentences = re.split(r"(?<=[.!?])\s+", text)
            for sent in sentences:
                if any(kw in sent.lower() for kw in workflow_keywords):
                    if len(sent) < 200:
                        snapshot.workflows.append(sent.strip())

        # 4. Synthesize Important Facts
        # We prioritize facts that mention the entities or query keywords
        q_words = set(query.lower().split())
        for chunk in chunks:
            text = chunk.text if hasattr(chunk, "text") else str(chunk)
            sentences = re.split(r"(?<=[.!?])\s+", text)
            for sent in sentences:
                words = set(sent.lower().split())
                if len(q_words & words) >= 1:
                    if len(sent) > 40 and len(sent) < 300:
                        snapshot.facts.append(sent.strip())

        # 5. Identify Contextual Relationships
        # Use site profile hints + chunk proximity
        site_rels = site_profile.get("relationships", [])
        snapshot.relationships.extend(site_rels)
        
        # Heuristic: If two entities appear in the same sentence, they are related
        for chunk in chunks:
            text = chunk.text if hasattr(chunk, "text") else str(chunk)
            sentences = re.split(r"(?<=[.!?])\s+", text)
            for sent in sentences:
                found_in_sent = [e for e in snapshot.entities if e in sent]
                if len(found_in_sent) >= 2:
                    rel = f"{found_in_sent[0]} is related to {found_in_sent[1]}"
                    if rel not in snapshot.relationships:
                        snapshot.relationships.append(rel)

        # 6. Extract Important Actions (verbs + entities)
        action_verbs = ["book", "apply", "register", "download", "install", "configure", "contact", "visit"]
        for chunk in chunks:
            text = chunk.text if hasattr(chunk, "text") else str(chunk)
            for verb in action_verbs:
                pattern = rf"\b{verb}\b\s+[^.!?]*"
                matches = re.findall(pattern, text, re.IGNORECASE)
                for m in matches:
                    if len(m.split()) < 10:
                        snapshot.important_actions.append(m.strip())

        # Final trimming to avoid bloat
        snapshot.facts = list(dict.fromkeys(snapshot.facts))[:10]
        snapshot.workflows = list(dict.fromkeys(snapshot.workflows))[:5]
        snapshot.relationships = list(dict.fromkeys(snapshot.relationships))[:8]
        snapshot.important_actions = list(dict.fromkeys(snapshot.important_actions))[:6]

        return snapshot
