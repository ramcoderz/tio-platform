from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.entities import Conversation, EmbeddingMetadata, Message, SessionMemory, UploadedDocument


async def get_or_create_conversation(
    db: AsyncSession,
    session_id: str,
    chatbot_id: int,
    user_id: int | None = None,
) -> Conversation:
    row = (await db.execute(
        select(Conversation).where(
            Conversation.session_id == session_id,
            Conversation.chatbot_id == chatbot_id
        )
    )).scalar_one_or_none()
    if row:
        return row
    row = Conversation(session_id=session_id, chatbot_id=chatbot_id, user_id=user_id)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row



async def get_conversation_by_session(db: AsyncSession, session_id: str, chatbot_id: int) -> Conversation | None:
    return (await db.execute(
        select(Conversation).where(
            Conversation.session_id == session_id,
            Conversation.chatbot_id == chatbot_id
        )
    )).scalar_one_or_none()


async def add_message(db: AsyncSession, conversation_id: int, role: str, content: str, citations: dict = None, confidence: float = 0.0):
    db.add(Message(
        conversation_id=conversation_id, 
        role=role, 
        content=content, 
        citations=citations or {}, 
        confidence=confidence
    ))
    await db.commit()


async def recent_history(db: AsyncSession, conversation_id: int, limit: int = 10) -> list[dict]:
    rows = (
        await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [{"role": r.role, "content": r.content, "sources": r.citations} for r in reversed(rows)]


async def get_all_history(db: AsyncSession, conversation_id: int) -> list[dict]:
    rows = (
        await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id.asc())
        )
    ).scalars().all()
    return [{"role": r.role, "content": r.content, "sources": r.citations, "confidence": r.confidence} for r in rows]


async def clear_session_state(db: AsyncSession, session_id: str) -> None:
    conv = (await db.execute(select(Conversation).where(Conversation.session_id == session_id))).scalar_one_or_none()
    if conv:
        await db.execute(delete(Message).where(Message.conversation_id == conv.id))
        await db.execute(delete(Conversation).where(Conversation.id == conv.id))
    await db.execute(delete(SessionMemory).where(SessionMemory.session_id == session_id))
    await db.commit()
