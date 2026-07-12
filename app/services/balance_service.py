from sqlalchemy.orm import Session
from app.models.group_member import GroupMember
from app.models.group import Group
from app.models.expense import Expense
from app.models.expense_split import ExpenseSplit
from app.models.user import User
from fastapi import HTTPException
from app.models.user import User
from app.services.authorization import check_group_membership
def get_group_balances(group_id: int, current_user, db: Session):

    # Verify group exists and current user is a member
    group = check_group_membership(db, group_id, current_user.id)

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