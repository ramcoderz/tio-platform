from backend.config.settings import get_settings

settings = get_settings()


def score_answer(answer: str, chunks: list) -> tuple[float, bool]:
    if not chunks:
        return 0.0, True
    retrieval_strength = sum(chunk.score for chunk in chunks) / len(chunks)
    answer_strength = min(1.0, len(answer) / 500)
    confidence = max(0.0, min(1.0, (retrieval_strength + answer_strength) / 2))
    return confidence, confidence < settings.confidence_threshold
