from sqlalchemy.orm import Session
from app.models.group_member import GroupMember
from app.models.group import Group
from app.models.expense import Expense
from app.models.expense_split import ExpenseSplit
from app.models.user import User
from fastapi import HTTPException
from app.models.user import User
def get_group_balances(group_id: int, db: Session):

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

    balances = {}

    members = (
        db.query(GroupMember)
        .filter(GroupMember.group_id == group_id)
        .all()
    )

    for member in members:

        user = (
            db.query(User)
            .filter(User.id == member.user_id)
            .first()
        )

        balances[user.id] = {
            "user_id": user.id,
            "username": user.username,
            "paid": 0,
            "owes": 0,
            "balance": 0
        }