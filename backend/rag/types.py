from dataclasses import dataclass


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    score: float
    document: str
    metadata: dict
    semantic_category: str = "General"
    match_explanation: str = ""
