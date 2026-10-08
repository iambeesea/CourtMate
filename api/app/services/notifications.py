from sqlalchemy.orm import Session

from ..models import Notification


def notify(db: Session, user_id: str, kind: str, title: str, body: str = "", link: str = "") -> None:
    """Queue an in-app notification inside the caller's transaction."""
    db.add(Notification(user_id=user_id, kind=kind, title=title[:160], body=body, link=link[:255]))


def notify_many(db: Session, user_ids: set[str] | list[str], kind: str, title: str, body: str = "", link: str = "") -> None:
    for user_id in set(user_ids):
        notify(db, user_id, kind, title, body, link)
