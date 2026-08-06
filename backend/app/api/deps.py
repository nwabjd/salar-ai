from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Conversation, Message, User
from ..security import get_current_user


def month_bounds(now: datetime) -> tuple[datetime, datetime]:
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def month_usage(db: Session, user_id: str) -> int:
    start, _end = month_bounds(datetime.now(timezone.utc))
    return (
        db.scalar(
            select(func.count(Message.id))
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(Conversation.user_id == user_id, Message.created_at >= start)
        )
        or 0
    )


def quota_status(db: Session, user: User, settings) -> dict:
    if user.is_admin:
        limit = None
    elif user.plan in ("pro", "team"):
        limit = settings.pro_monthly_quota
    else:
        limit = settings.free_monthly_quota
    used = month_usage(db, user.id)
    _start, reset_at = month_bounds(datetime.now(timezone.utc))
    return {
        "plan": user.plan,
        "limit": limit,
        "used": used,
        "reset_at": reset_at.isoformat(),
        "exempt": user.is_admin,
    }


def check_quota(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    quota = quota_status(db, user, request.app.state.settings)
    limit = quota["limit"]
    if limit is not None and quota["used"] >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "quota_exceeded": True,
                "used": quota["used"],
                "limit": limit,
                "reset_at": quota["reset_at"],
            },
        )
    return quota
