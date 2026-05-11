from datetime import datetime
from functools import wraps
from typing import Any, Callable

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.models.entities import AuditLog, User


from backend.utils.cache import semantic_cache

async def log_activity(
    db: AsyncSession,
    user_id: int | None,
    action: str,
    resource: str | None = None,
    details: str | None = None,
    ip_address: str | None = None,
):
    timestamp = datetime.utcnow()
    audit_entry = AuditLog(
        user_id=user_id,
        action=action,
        resource=resource,
        details=details,
        ip_address=ip_address,
        timestamp=timestamp,
    )
    db.add(audit_entry)
    await db.commit()
    
    # Push to real-time activity feed
    await semantic_cache.push_activity({
        "timestamp": timestamp.isoformat(),
        "action": action,
        "resource": resource,
        "details": details
    })


def audit_logger(action: str, resource_name: str | None = None):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request and user if available
            request: Request = kwargs.get("request")
            current_user: User = kwargs.get("current_user")
            db: AsyncSession = kwargs.get("db")

            user_id = current_user.id if current_user else None
            ip_address = request.client.host if request else None

            # Execute the function
            result = await func(*args, **kwargs)

            # Log after execution if successful
            if db:
                await log_activity(
                    db=db,
                    user_id=user_id,
                    action=action,
                    resource=resource_name,
                    details=f"Success: {func.__name__}",
                    ip_address=ip_address,
                )
            
            return result
        return wrapper
    return decorator
