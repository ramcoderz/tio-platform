from backend.validation.validator import score_answer


async def validate(answer: str, chunks: list):
    return score_answer(answer, chunks)
