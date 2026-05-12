from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.models.entities import Chatbot
import logging

logger = logging.getLogger(__name__)

async def seed_chatbots(db: AsyncSession):
    """Seed the database with pre-created starter chatbots."""
    starter_bots = [
        {
            "name": "Global Travel Guide",
            "domain": "tourism",
            "behavior_profile": "tourism",
            "status": "ready",
            "config": {"welcome_message": "Ready to plan your next adventure? I can help with itineraries and recommendations!"}
        },
        {
            "name": "Academic Scholar",
            "domain": "education",
            "behavior_profile": "education",
            "status": "ready",
            "config": {"welcome_message": "Welcome! I can assist you with course information and academic resources."}
        },
        {
            "name": "Medical Advisor",
            "domain": "medical",
            "behavior_profile": "medical",
            "status": "ready",
            "config": {"welcome_message": "I'm here to provide grounded medical information and answer health-related queries."}
        },
        {
            "name": "Dev Documentation Bot",
            "domain": "developer",
            "behavior_profile": "developer",
            "status": "ready",
            "config": {"welcome_message": "Technical docs at your service. How can I help with your integration today?"}
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
