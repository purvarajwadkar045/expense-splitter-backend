from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.notification import Notification


def create_notification(db: Session, user_id: int, title: str, message: str) -> Notification:
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        is_read=False
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def get_user_notifications(db: Session, current_user, page: int = 1, limit: int = 10):
    if page <= 0:
        raise HTTPException(status_code=400, detail="Page must be greater than 0")
    if limit <= 0:
        raise HTTPException(status_code=400, detail="Limit must be greater than 0")

    offset = (page - 1) * limit
    return (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def mark_as_read(db: Session, current_user, notification_id: int) -> Notification:
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    if notification.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied")

    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification


def mark_all_as_read(db: Session, current_user):
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).update({Notification.is_read: True}, synchronize_session=False)
    db.commit()
    return {"message": "All notifications marked as read"}


def delete_notification(db: Session, current_user, notification_id: int):
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    if notification.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied")

    db.delete(notification)
    db.commit()
    return {"message": "Notification deleted successfully"}
