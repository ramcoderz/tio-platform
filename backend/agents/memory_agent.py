from backend.models.entities import SessionMemory


async def store_memory(db, session_id: str, chatbot_id: int, key: str, value: str) -> None:
    db.add(SessionMemory(session_id=session_id, chatbot_id=chatbot_id, key=key, value=value))
    await db.commit()
