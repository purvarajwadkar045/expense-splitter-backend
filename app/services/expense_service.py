from datetime import datetime
from typing import Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload
from app.models.expense import Expense
from app.models.group import Group
from app.models.group_member import GroupMember
from app.models.expense_split import ExpenseSplit
from app.services.authorization import check_group_membership

def create_expense(group_id, expense_data, current_user, db):
    # Verify group exists and current user is a member
    check_group_membership(db, group_id, current_user.id)

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

    # Verify group exists and current user is a member
    check_group_membership(db, group_id, current_user.id)

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


def update_expense(expense_id: int, expense_data, current_user, db: Session):
    # 1. Validate that the expense exists
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    # 2. Validate that the authenticated user has permission (Only the user who created/paid for the expense)
    if expense.paid_by != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied")

    # 3. Reject amount <= 0 if provided
    if expense_data.amount is not None and expense_data.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than 0")

    # 4. Update the expense record
    if expense_data.title is not None:
        expense.title = expense_data.title
    if expense_data.amount is not None:
        expense.amount = expense_data.amount
    if expense_data.description is not None:
        expense.description = expense_data.description

    # Fetch old participants list before deleting the splits
    old_splits = db.query(ExpenseSplit).filter(ExpenseSplit.expense_id == expense.id).all()
    old_participant_ids = [split.user_id for split in old_splits]

    # 5. Remove old ExpenseSplit records
    db.query(ExpenseSplit).filter(ExpenseSplit.expense_id == expense.id).delete()

    # 6. Recalculate and recreate ExpenseSplit records
    if expense_data.participants is not None:
        participants = expense_data.participants
        if not participants:
            raise HTTPException(status_code=400, detail="Participants list cannot be empty")
        if len(participants) != len(set(participants)):
            raise HTTPException(status_code=400, detail="Duplicate participants found")
        # Validate that each participant is a member of the group
        for p_id in participants:
            member = db.query(GroupMember).filter(
                GroupMember.group_id == expense.group_id,
                GroupMember.user_id == p_id
            ).first()
            if not member:
                raise HTTPException(status_code=400, detail=f"User {p_id} is not a member of this group")
    else:
        # If participants list is not provided:
        if old_participant_ids:
            participants = old_participant_ids
        else:
            # Fallback to all group members
            members = db.query(GroupMember).filter(GroupMember.group_id == expense.group_id).all()
            participants = [m.user_id for m in members]

    if participants:
        share = expense.amount / len(participants)
        for p_id in participants:
            split = ExpenseSplit(
                expense_id=expense.id,
                user_id=p_id,
                amount=share
            )
            db.add(split)

    db.commit()
    db.refresh(expense)
    return expense


def delete_expense(expense_id: int, current_user, db: Session):
    # 1. Validate that the expense exists
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    # 2. Validate that the authenticated user has permission
    if expense.paid_by != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied")

    # 3. Delete associated ExpenseSplit records first
    db.query(ExpenseSplit).filter(ExpenseSplit.expense_id == expense.id).delete()

    # 4. Delete the Expense
    db.delete(expense)
    db.commit()

