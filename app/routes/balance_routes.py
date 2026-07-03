from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies.db import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.balance import BalanceResponse
from app.services.balance_service import get_group_balances

router = APIRouter(
    prefix="/groups",
    tags=["Balances"]
)


@router.get(
    "/{group_id}/balances",
    response_model=list[BalanceResponse]
)
def group_balances(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return get_group_balances(group_id, db)