from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.dependencies.db import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.settlement import SettlementCreate, SettlementResponse
from app.services import settlement_service

router = APIRouter(prefix="/groups", tags=["Settlements"])

@router.post("/{group_id}/settlements", response_model=SettlementResponse)
def create_settlement(
    group_id: int,
    settlement: SettlementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return settlement_service.create_settlement(group_id, settlement, current_user, db)

@router.get("/{group_id}/settlements", response_model=list[SettlementResponse])
def get_settlement_history(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return settlement_service.get_settlement_history(group_id, current_user, db)
