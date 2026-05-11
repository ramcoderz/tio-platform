from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.models.entities import Task

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/")
async def get_tasks(session_id: str | None = None, db: AsyncSession = Depends(get_db)):
    query = select(Task)
    if session_id:
        query = query.where(Task.session_id == session_id)
    
    rows = (await db.execute(query)).scalars().all()
    return [
        {
            "id": r.id,
            "session_id": r.session_id,
            "description": r.description,
            "owner": r.owner,
            "deadline": r.deadline,
            "status": r.status,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
