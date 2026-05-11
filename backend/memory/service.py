from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.entities import Conversation, EmbeddingMetadata, Message, RetrievalLog, SessionMemory, InferenceMetric, UploadedDocument


async def conversation(db: AsyncSession, session_id: str) -> Conversation:
    row = (await db.execute(select(Conversation).where(Conversation.session_id == session_id))).scalar_one_or_none()
    if row:
        return row
    row = Conversation(session_id=session_id)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def add_message(db: AsyncSession, conversation_id: int, role: str, content: str, citations: dict, confidence: float):
    db.add(Message(conversation_id=conversation_id, role=role, content=content, citations=citations, confidence=confidence))
    await db.commit()


async def recent_history(db: AsyncSession, conversation_id: int, limit: int = 8) -> list[dict]:
    rows = (
        await db.execute(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id.desc()).limit(limit))
    ).scalars().all()
    return [{"role": r.role, "content": r.content, "sources": r.citations, "confidence": r.confidence} for r in reversed(rows)]

async def get_all_history(db: AsyncSession, conversation_id: int) -> list[dict]:
    rows = (
        await db.execute(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id.asc()))
    ).scalars().all()
    return [{"role": r.role, "content": r.content, "sources": r.citations, "confidence": r.confidence} for r in rows]


async def clear_session_state(db: AsyncSession, session_id: str, chunk_ids: list[str]) -> None:
    docs = (
        await db.execute(
            select(SessionMemory.value).where(
                SessionMemory.session_id == session_id, SessionMemory.key == "uploaded_document_id"
            )
        )
    ).scalars().all()

    conv = (await db.execute(select(Conversation).where(Conversation.session_id == session_id))).scalar_one_or_none()
    if conv:
        await db.execute(delete(Message).where(Message.conversation_id == conv.id))
        await db.execute(delete(Conversation).where(Conversation.id == conv.id))
    await db.execute(delete(SessionMemory).where(SessionMemory.session_id == session_id))
    await db.execute(delete(RetrievalLog).where(RetrievalLog.session_id == session_id))
    await db.execute(delete(InferenceMetric).where(InferenceMetric.session_id == session_id))

    if chunk_ids:
        await db.execute(delete(EmbeddingMetadata).where(EmbeddingMetadata.chunk_id.in_(chunk_ids)))

    if docs:
        doc_ids = [int(doc_id) for doc_id in docs if str(doc_id).isdigit()]
        if doc_ids:
            await db.execute(delete(UploadedDocument).where(UploadedDocument.id.in_(doc_ids)))
    await db.commit()
