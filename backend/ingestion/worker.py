import asyncio
import logging
from datetime import datetime
from sqlalchemy import select, update
from backend.db.session import SessionLocal
from backend.models.entities import Chatbot, IngestionJob

logger = logging.getLogger(__name__)
from backend.utils.console import console

class IngestionWorker:
    def __init__(self, concurrency=2):
        self.queue = asyncio.Queue()
        self.semaphore = asyncio.Semaphore(concurrency)
        self._worker_task = None

    async def start(self):
        """Start the background worker loop."""
        if self._worker_task:
            return
        self._worker_task = asyncio.create_task(self._run())
        logger.info("[WORKER] Ingestion worker initialized and running.")
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self):
        """Continuous heartbeat and auto-recovery loop."""
        while True:
            try:
                await asyncio.sleep(20)
                # Heartbeat logging
                print(flush=True)
                print("========================================================", flush=True)
                print("[WORKER]", flush=True)
                print("Ingestion worker heartbeat OK", flush=True)
                print("========================================================", flush=True)
                print(flush=True)

                # Auto-recovery if processor task died
                if self._worker_task is None or self._worker_task.done():
                    print("========================================================", flush=True)
                    print("[FATAL]", flush=True)
                    print("Ingestion worker disconnected", flush=True)
                    print("========================================================", flush=True)
                    print("[SYSTEM] Attempting auto-recovery of background worker...", flush=True)
                    self._worker_task = asyncio.create_task(self._run())
                    print("[SYSTEM] Background worker recovered and active.", flush=True)
                    print(flush=True)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[WORKER] Heartbeat/auto-recovery error: {e}")

    async def submit_job(self, chatbot_id: int):
        """Submit a new ingestion job to the queue and persist its initial state."""
        async with SessionLocal() as db:
            # Create a dedicated job record for lifecycle tracking
            job = IngestionJob(
                chatbot_id=chatbot_id, 
                status="pending",
                current_stage="queued",
                progress=0
            )
            db.add(job)
            await db.commit()
            await db.refresh(job)
            
            await self.queue.put(job.id)
            console.info(f"Job {job.id} queued for chatbot {chatbot_id}")
            return job.id

    async def _run(self):
        """Infinite worker loop that processes jobs from the queue."""
        while True:
            try:
                job_id = await self.queue.get()
                # Spawn a non-blocking task for each job
                asyncio.create_task(self._process_job_id(job_id))
            except Exception as e:
                logger.error(f"[WORKER] Fatal error in worker loop: {e}")
                await asyncio.sleep(5) # Cooldown before restart

    async def _process_job_id(self, job_id: int):
        """Manages the lifecycle of a single ingestion job with concurrency control."""
        async with self.semaphore:
            async with SessionLocal() as db:
                job = await db.get(IngestionJob, job_id)
                if not job:
                    logger.error(f"[WORKER] Job {job_id} not found.")
                    return

                console.stage("INGESTING", f"Starting Job {job_id} for Chatbot {job.chatbot_id}")
                
                try:
                    # 1. Mark as active
                    job.status = "ingesting"
                    job.started_at = datetime.utcnow()
                    
                    chatbot = await db.get(Chatbot, job.chatbot_id)
                    if chatbot:
                        chatbot.status = "ingesting"
                    
                    await db.commit()

                    # 2. Execute with safety timeout
                    from backend.ingestion.service import ingest_website_core
                    await asyncio.wait_for(
                        ingest_website_core(job.chatbot_id, job_id),
                        timeout=900 # 15 min cap
                    )

                    # 3. Finalize success (re-fetch to avoid stale state)
                    await db.refresh(job)
                    job.status = "ready"
                    job.progress = 100
                    job.completed_at = datetime.utcnow()
                    
                    # Ensure chatbot is also marked ready
                    chatbot = await db.get(Chatbot, job.chatbot_id)
                    if chatbot:
                        chatbot.status = "ready"
                    
                    await db.commit()
                    console.success(f"Job {job_id} finalized as READY.")

                except asyncio.TimeoutError:
                    err = "Ingestion timed out after 15 minutes."
                    console.critical(f"Job {job_id} timeout reached (15m cap).")
                    await self._mark_job_failed(job_id, err)
                except Exception as e:
                    err = str(e)
                    console.error(f"Job {job_id} failed with exception: {err}")
                    await self._mark_job_failed(job_id, err)
                finally:
                    self.queue.task_done()

    async def _mark_job_failed(self, job_id: int, error: str):
        """Guaranteed finalization to 'error' state."""
        try:
            async with SessionLocal() as db:
                job = await db.get(IngestionJob, job_id)
                if job:
                    job.status = "error"
                    job.error_message = error
                    job.completed_at = datetime.utcnow()
                    
                    chatbot = await db.get(Chatbot, job.chatbot_id)
                    if chatbot:
                        chatbot.status = "error"
                        chatbot.error_message = f"Ingestion failed: {error}"
                        # Clear any pulsing/stuck status_json
                        chatbot.status_json = {
                            "stage": "failed",
                            "progress": 0,
                            "message": f"Failed: {error[:100]}",
                            "error": True
                        }
                    await db.commit()
                    logger.info(f"[WORKER] Job {job_id} marked as FAILED.")
        except Exception as e:
            logger.error(f"[WORKER] Fatal failure marking job {job_id} as failed: {e}")

# Global singleton instance
ingestion_worker = IngestionWorker(concurrency=2)
