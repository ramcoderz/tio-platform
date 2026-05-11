import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select, delete
from backend.db.session import SessionLocal
from backend.models.entities import UploadedDocument, EmbeddingMetadata, SystemConfig
from backend.vectorstore.service import delete_chunk_vectors
from backend.config.settings import get_settings
import os

settings = get_settings()

async def auto_cleanup_worker():
    """Background worker that purges expired documents every hour."""
    print(f"Starting auto-cleanup worker (Retention: {settings.auto_delete_hours}h)")
    while True:
        try:
            async with SessionLocal() as db:
                # Get dynamic retention setting
                config_stmt = select(SystemConfig).where(SystemConfig.key == "auto_delete_hours")
                config_row = (await db.execute(config_stmt)).scalar_one_or_none()
                retention_hours = int(config_row.value) if config_row else settings.auto_delete_hours
                
                print(f"Running auto-cleanup (Retention: {retention_hours}h)")
                
                threshold = datetime.utcnow() - timedelta(hours=retention_hours)
                
                # Fetch expired docs
                stmt = select(UploadedDocument).where(UploadedDocument.created_at < threshold)
                result = await db.execute(stmt)
                expired_docs = result.scalars().all()
                
                for doc in expired_docs:
                    print(f"Auto-deleting expired document: {doc.filename} (ID: {doc.id})")
                    
                    # 1. Get chunk IDs for vector deletion
                    chunks_stmt = select(EmbeddingMetadata.chunk_id).where(EmbeddingMetadata.document_id == doc.id)
                    chunk_ids = (await db.execute(chunks_stmt)).scalars().all()
                    
                    # 2. Delete vectors
                    if chunk_ids:
                        await asyncio.to_thread(delete_chunk_vectors, list(chunk_ids))
                    
                    # 3. Delete metadata and relationships (handled by cascade if set, but we'll do it manually to be safe)
                    await db.execute(delete(EmbeddingMetadata).where(EmbeddingMetadata.document_id == doc.id))
                    
                    # 4. Delete physical file
                    if os.path.exists(doc.source_path):
                        os.remove(doc.source_path)
                        
                    # 5. Delete document record
                    await db.delete(doc)
                
                await db.commit()
                
        except Exception as e:
            print(f"Auto-cleanup error: {e}")
            
        await asyncio.sleep(3600) # Run every hour
