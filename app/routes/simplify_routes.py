from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.dependencies.db import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.simplify import SimplifyTransaction
from app.services import simplify_service

router = APIRouter(
    prefix="/groups",
    tags=["Simplify"]
)

@router.get(
    "/{group_id}/simplify",
    response_model=List[SimplifyTransaction]
)
def simplify_group_debts(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return simplify_service.simplify_debts(group_id, current_user, db)
