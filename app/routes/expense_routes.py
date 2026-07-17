from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.dependencies.db import get_db
from app.dependencies.auth import get_current_user
from app.schemas.expense import ExpenseCreate, ExpenseResponse, ExpenseHistoryResponse, ExpenseUpdate
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
    user_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    page: int = 1,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return expense_service.get_group_expenses(
        group_id=group_id,
        current_user=current_user,
        db=db,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        page=page,
        limit=limit
    )


expense_direct_router = APIRouter(prefix="/expenses", tags=["Expenses"])


@expense_direct_router.put("/{expense_id}", response_model=ExpenseResponse)
def update_expense(
    expense_id: int,
    expense_data: ExpenseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return expense_service.update_expense(expense_id, expense_data, current_user, db)


@expense_direct_router.delete("/{expense_id}")
def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    expense_service.delete_expense(expense_id, current_user, db)
    return {"message": "Expense deleted successfully"}
