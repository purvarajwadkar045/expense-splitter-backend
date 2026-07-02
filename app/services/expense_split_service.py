from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.group import Group
from app.models.group_member import GroupMember
from app.models.expense import Expense
from app.models.expense_split import ExpenseSplit
from app.models.user import User
from app.schemas.expense_split import EqualExpenseCreate


def create_equal_expense(
    group_id: int,
    expense_data: EqualExpenseCreate,
    current_user: User,
    db: Session
):
    group = (
        db.query(Group)
        .filter(Group.id == group_id)
        .first()
    )

    if not group:
        raise HTTPException(
            status_code=404,
            detail="Group not found"
        )

    if expense_data.amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Amount must be greater than zero"
        )

    if not expense_data.participants:
        raise HTTPException(
            status_code=400,
            detail="Participants list cannot be empty"
        )

    if len(expense_data.participants) != len(set(expense_data.participants)):
        raise HTTPException(
            status_code=400,
            detail="Duplicate participants found"
        )

    for participant_id in expense_data.participants:

        member = (
            db.query(GroupMember)
            .filter(
                GroupMember.group_id == group_id,
                GroupMember.user_id == participant_id
            )
            .first()
        )

        if not member:
            raise HTTPException(
                status_code=400,
                detail=f"User {participant_id} is not a member of this group"
            )

    expense = Expense(
        title=expense_data.title,
        amount=expense_data.amount,
        description=expense_data.description,
        group_id=group_id,
        paid_by=current_user.id
    )

    db.add(expense)
    db.flush()

    share = expense_data.amount / len(expense_data.participants)

    for participant_id in expense_data.participants:

        split = ExpenseSplit(
            expense_id=expense.id,
            user_id=participant_id,
            amount=share
        )

        db.add(split)

    db.commit()
    db.refresh(expense)

    return expense