from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.models.entities import Chatbot
import logging

logger = logging.getLogger(__name__)

async def seed_chatbots(db: AsyncSession):
    """Seed the database with pre-created starter chatbots."""
    starter_bots = [
        {
            "name": "MVIT",
            "website_url": "https://mvit.edu.in",
            "domain": "education",
            "behavior_profile": "education",
            "status": "ready",
            "is_permanent": 1
        },
        {
            "name": "NASA",
            "website_url": "https://www.nasa.gov",
            "domain": "general",
            "behavior_profile": "general",
            "status": "ready",
            "is_permanent": 1
        },
        {
            "name": "Pondicherry Tourism",
            "website_url": "https://tourism.gov.in",
            "domain": "tourism",
            "behavior_profile": "tourism",
            "status": "ready",
            "is_permanent": 1
        },
        {
            "name": "FastAPI Docs",
            "website_url": "https://fastapi.tiangolo.com",
            "domain": "developer",
            "behavior_profile": "developer",
            "status": "ready",
            "is_permanent": 1
        },
        {
            "name": "Ollama Docs",
            "website_url": "https://ollama.com",
            "domain": "developer",
            "behavior_profile": "developer",
            "status": "ready",
            "is_permanent": 1
        }
    ]

    for bot_data in starter_bots:
        stmt = select(Chatbot).where(Chatbot.name == bot_data["name"])
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if not existing:
            bot = Chatbot(**bot_data)
            db.add(bot)
            logger.info(f"Seeded starter chatbot: {bot_data['name']}")
    
    await db.commit()
