from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.dependencies.db import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.activity import ActivityResponse
from app.services import activity_service


router = APIRouter(
    prefix="/groups",
    tags=["Activity"]
)


@router.get(
    "/{group_id}/activity",
    response_model=List[ActivityResponse]
)
def get_group_activity_timeline(
    group_id: int,
    page: int = 1,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return activity_service.get_group_activities(
        group_id=group_id,
        current_user=current_user,
        db=db,
        page=page,
        limit=limit
    )
