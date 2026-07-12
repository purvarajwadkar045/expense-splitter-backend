from datetime import datetime
from typing import Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload
from app.models.expense import Expense
from app.models.group import Group
from app.models.group_member import GroupMember

def create_expense(group_id, expense_data, current_user, db):
    # Verify group exists
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # Verify current user is a member of the group
    is_member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == current_user.id
    ).first()
    
    if not is_member:
        raise HTTPException(status_code=403, detail="User is not a member of this group")

    # Reject amount <= 0
    if expense_data.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than 0")

    # Create Expense
    expense = Expense(
        title=expense_data.title,
        amount=expense_data.amount,
        description=expense_data.description,
        group_id=group_id,
        paid_by=current_user.id
    )

    db.add(expense)
    db.commit()
    db.refresh(expense)
    
    return expense


def get_group_expenses(
    group_id: int,
    current_user,
    db: Session,
    user_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    page: int = 1,
    limit: int = 10
):
    # Validate page and limit values
    if page <= 0:
        raise HTTPException(status_code=400, detail="Page must be greater than 0")
    if limit <= 0:
        raise HTTPException(status_code=400, detail="Limit must be greater than 0")

    # Verify group exists
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # Verify current user is a member of the group
    is_member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == current_user.id
    ).first()
    
    if not is_member:
        raise HTTPException(status_code=403, detail="User is not a member of this group")

    # Build Query with filters
    query = (
        db.query(Expense)
        .options(joinedload(Expense.payer))
        .filter(Expense.group_id == group_id)
    )

    if user_id is not None:
        query = query.filter(Expense.paid_by == user_id)
    if start_date is not None:
        query = query.filter(Expense.created_at >= start_date)
    if end_date is not None:
        query = query.filter(Expense.created_at <= end_date)

    # Retrieve expenses ordered by newest first with pagination
    offset = (page - 1) * limit
    expenses = (
        query.order_by(Expense.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        {
            "id": exp.id,
            "title": exp.title,
            "description": exp.description,
            "amount": exp.amount,
            "paid_by": exp.payer.username if exp.payer else "Unknown",
            "created_at": exp.created_at
        }
        for exp in expenses
    ]

