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

        # 1. Extract and Deduplicate Entities from metadata or heuristic
        seen_entities = set()
        entity_to_doc = {}
        
        for chunk in chunks:
            meta = getattr(chunk, "metadata", {})
            ents = meta.get("entities", [])
            doc = getattr(chunk, "document", "Unknown")
            
            if not ents:
                text = chunk.text if hasattr(chunk, "text") else str(chunk)
                ents = re.findall(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*\b", text)
            
            for ent in ents:
                if len(ent) > 3 and ent.lower() not in ["the", "this", "that"]:
                    seen_entities.add(ent)
                    if ent not in entity_to_doc:
                        entity_to_doc[ent] = doc
        
        snapshot.entities = sorted(list(seen_entities))[:15]

        # 2. Identify Related Pages (Source Attribution)
        pages = set()
        for chunk in chunks:
            doc = getattr(chunk, "document", "Unknown")
            if doc and doc != "Unknown":
                pages.add(doc)
        snapshot.related_pages = list(pages)

        # 3. Detect Workflows (Keyword + Domain context)
        workflow_keywords = ["step", "first", "then", "finally", "how to", "process", "guide", "setup", "integrate", "apply", "requirements"]
        for chunk in chunks:
            text = chunk.text if hasattr(chunk, "text") else str(chunk)
            sentences = re.split(r"(?<=[.!?])\s+", text)
            for sent in sentences:
                if any(kw in sent.lower() for kw in workflow_keywords):
                    if len(sent) < 200:
                        snapshot.workflows.append(sent.strip())

        # 4. Synthesize Important Facts
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
        site_rels = site_profile.get("relationships", [])
        snapshot.relationships.extend(site_rels)
        
        # Link entities to their documents
        for ent, doc in entity_to_doc.items():
            if ent in snapshot.entities:
                snapshot.relationships.append(f"{ent} is mentioned in {doc}")

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
        action_verbs = ["book", "apply", "register", "download", "install", "configure", "contact", "visit", "work", "graduate", "publish"]
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
        snapshot.relationships = list(dict.fromkeys(snapshot.relationships))[:10]
        snapshot.important_actions = list(dict.fromkeys(snapshot.important_actions))[:6]

        return snapshot
