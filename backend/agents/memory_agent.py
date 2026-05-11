from backend.models.entities import SessionMemory


async def store_memory(db, session_id: str, key: str, value: str) -> None:
    db.add(SessionMemory(session_id=session_id, key=key, value=value))
    await db.commit()
