from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.dependencies.db import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.notification import NotificationResponse
from app.services import notification_service


router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"]
)


@router.get(
    "",
    response_model=List[NotificationResponse]
)
def get_notifications(
    page: int = 1,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return notification_service.get_user_notifications(
        db=db,
        current_user=current_user,
        page=page,
        limit=limit
    )


@router.patch(
    "/read-all"
)
def read_all_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return notification_service.mark_all_as_read(db=db, current_user=current_user)


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse
)
def read_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return notification_service.mark_as_read(
        db=db,
        current_user=current_user,
        notification_id=notification_id
    )


@router.delete(
    "/{notification_id}"
)
def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return notification_service.delete_notification(
        db=db,
        current_user=current_user,
        notification_id=notification_id
    )
