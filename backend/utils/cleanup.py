import os
import asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.entities import Chatbot, UploadedDocument, Conversation, Message, EmbeddingMetadata, SessionMemory
from backend.vectorstore.service import delete_chatbot_vectors, delete_chunk_vectors

async def deep_delete_chatbot(chatbot_id: int, db: AsyncSession):
    """
    Production-grade deep cleanup for a chatbot.
    Removes:
    - Physical files
    - Vector embeddings (Chroma/FAISS)
    - Session memory
    - DB records (Documents, Metadata, Conversations, Messages, Chatbot)
    """
    chatbot = await db.get(Chatbot, chatbot_id)
    if not chatbot:
        return

    # 1. Physical file cleanup
    docs = (await db.execute(
        select(UploadedDocument).where(UploadedDocument.chatbot_id == chatbot_id)
    )).scalars().all()
    for d in docs:
        if d.source_path and os.path.exists(d.source_path):
            try:
                os.remove(d.source_path)
            except Exception:
                pass

    # 2. Vector cleanup
    await asyncio.to_thread(delete_chatbot_vectors, chatbot_id)

    # 3. Session memory cleanup
    await db.execute(delete(SessionMemory).where(SessionMemory.chatbot_id == chatbot_id))

    # 4. DB cleanup (cascades handle conversations/messages)
    await db.delete(chatbot)
    await db.commit()
