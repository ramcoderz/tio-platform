import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy import select
from backend.db.session import SessionLocal
from backend.models.entities import Chatbot
from backend.ingestion.service import ingest_website

logger = logging.getLogger(__name__)

async def start_refresh_scheduler():
    """
    Very simple periodic refresh scheduler.
    In a real production environment, this would use Celery Beat or a CRON job.
    """
    logger.info("[SCHEDULER] Starting background refresh worker...")
    
    while True:
        try:
            # Sleep for 12 hours between checks
            await asyncio.sleep(12 * 3600)
            
            async with SessionLocal() as db:
                # Find chatbots that have a website_url and haven't been updated in 7 days
                # Or just any chatbot that is 'ready' and has a refresh enabled (if we had a flag)
                # For MVP, let's just log and refresh a subset or skip for now to avoid infinite loops.
                
                stmt = select(Chatbot).where(Chatbot.website_url.isnot(None), Chatbot.status == "ready")
                result = await db.execute(stmt)
                chatbots = result.scalars().all()
                
                for chatbot in chatbots:
                    # Bounded crawling: only refresh if explicitly requested or on a long schedule
                    logger.info(f"[SCHEDULER] Auto-refreshing chatbot {chatbot.id} ({chatbot.name})")
                    # In a real app, we might check chatbot.last_ingested_at
                    asyncio.create_task(ingest_website(chatbot.id, chatbot.website_url))
                    
        except Exception as e:
            logger.error(f"[SCHEDULER] Error in refresh loop: {e}")
            await asyncio.sleep(60) # wait a bit before retrying on error
