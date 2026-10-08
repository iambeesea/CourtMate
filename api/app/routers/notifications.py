from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .. import schemas
from ..db import get_db
from ..models import Notification, User, utcnow
from ..security import current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _unread(db: Session, user: User) -> int:
    return (
        db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None)))
        or 0
    )


@router.get("", response_model=schemas.NotificationList)
def list_notifications(limit: int = Query(default=30, ge=1, le=100), user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The signed-in player's notifications, newest first, with the unread count."""
    items = db.scalars(
        select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc(), Notification.id).limit(limit)
    ).all()
    return schemas.NotificationList(unread=_unread(db, user), items=list(items))


@router.post("/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read(payload: schemas.MarkReadIn | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Mark the given notifications read, or all of them when no ids are sent."""
    statement = update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None)).values(read_at=utcnow())
    if payload and payload.ids is not None:
        statement = statement.where(Notification.id.in_(payload.ids))
    db.execute(statement, execution_options={"synchronize_session": False})
    db.commit()
