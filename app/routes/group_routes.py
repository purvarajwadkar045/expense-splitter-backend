from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies.db import get_db
from app.schemas.group import GroupCreate, GroupResponse, AddMember
from app.services import group_service
from app.dependencies.auth import get_current_user
from app.models.user import User

router = APIRouter(
    prefix="/groups",
    tags=["Groups"]
)


@router.post(
    "",
    response_model=GroupResponse
)
def create_group(
    group: GroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return group_service.create_group(
        group,
        current_user,
        db
    )


@router.post("/{group_id}/members")
def add_member(
    group_id: int,
    member: AddMember,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return group_service.add_member(
        group_id,
        member.email,
        current_user,
        db
    )