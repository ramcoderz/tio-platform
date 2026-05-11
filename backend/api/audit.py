from fastapi import APIRouter, Depends
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import check_role
from backend.db.session import get_db
from backend.models.entities import AuditLog

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs", dependencies=[Depends(check_role("admin"))])
async def get_audit_logs(limit: int = 100, db: AsyncSession = Depends(get_db)):
    query = select(AuditLog).order_by(desc(AuditLog.timestamp)).limit(limit)
    rows = (await db.execute(query)).scalars().all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "action": r.action,
            "resource": r.resource,
            "details": r.details,
            "ip_address": r.ip_address,
            "timestamp": r.timestamp.isoformat(),
        }
        for r in rows
    ]
