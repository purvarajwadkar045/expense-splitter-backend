from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.dependencies.db import get_db
from app.dependencies.auth import get_current_user
from app.schemas.expense import ExpenseCreate, ExpenseResponse, ExpenseHistoryResponse
from app.services import expense_service
from app.models.user import User

router = APIRouter(prefix="/groups", tags=["Expenses"])

@router.post("/{group_id}/expenses", response_model=ExpenseResponse)
def create_expense(
    group_id: int,
    expense: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return expense_service.create_expense(group_id, expense, current_user, db)

@router.get("/{group_id}/expenses", response_model=list[ExpenseHistoryResponse])
def get_group_expenses(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return expense_service.get_group_expenses(group_id, current_user, db)

