from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
import auth, models

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def add_notification(db, recipient_id, event_type, title, message, challenge_id=None, solution_id=None, workspace_id=None):
    if not recipient_id:
        return
    db.add(models.Notification(
        recipient_id=recipient_id,
        challenge_id=challenge_id,
        solution_id=solution_id,
        workspace_id=workspace_id,
        event_type=event_type,
        title=title,
        message=message,
    ))


def add_role_notifications(db, roles, event_type, title, message, challenge_id=None, solution_id=None, workspace_id=None):
    recipients = db.query(models.User).filter(models.User.role.in_(roles)).all()
    for recipient in recipients:
        add_notification(db, recipient.id, event_type, title, message, challenge_id, solution_id, workspace_id)


@router.get("/mine")
def my_notifications(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    items = db.query(models.Notification).filter(
        models.Notification.recipient_id == current_user.id
    ).order_by(models.Notification.created_at.desc()).limit(50).all()
    return [{
        "id": item.id,
        "challenge_id": item.challenge_id,
        "solution_id": item.solution_id,
        "workspace_id": item.workspace_id,
        "event_type": item.event_type,
        "title": item.title,
        "message": item.message,
        "is_read": item.is_read,
        "created_at": item.created_at,
    } for item in items]


@router.patch("/{notification_id}/read")
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    item = db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.recipient_id == current_user.id,
    ).first()
    if item:
        item.is_read = True
        db.commit()
    return {"ok": True}