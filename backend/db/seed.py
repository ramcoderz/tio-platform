from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.models.entities import Chatbot
import logging

logger = logging.getLogger(__name__)

async def seed_chatbots(db: AsyncSession):
    """Seed the database with pre-created starter chatbots."""
    starter_bots = []

    for bot_data in starter_bots:
        stmt = select(Chatbot).where(Chatbot.name == bot_data["name"])
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if not existing:
            bot = Chatbot(**bot_data)
            db.add(bot)
            logger.info(f"Seeded starter chatbot: {bot_data['name']}")
    
    await db.commit()
