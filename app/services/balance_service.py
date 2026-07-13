from sqlalchemy.orm import Session
from app.models.group_member import GroupMember
from app.models.group import Group
from app.models.expense import Expense
from app.models.expense_split import ExpenseSplit
from app.models.user import User
from app.models.settlement import Settlement
from fastapi import HTTPException
from app.services.authorization import check_group_membership

def get_group_balances(group_id: int, current_user, db: Session):
    # Verify group exists and current user is a member
    group = check_group_membership(db, group_id, current_user.id)

    balances = {}
    members = db.query(GroupMember).filter(GroupMember.group_id == group_id).all()

    for member in members:
        user = db.query(User).filter(User.id == member.user_id).first()
        balances[user.id] = {
            "user_id": user.id,
            "username": user.username,
            "paid": 0.0,
            "owes": 0.0,
            "balance": 0.0
        }

    # Fetch all expenses in the group
    expenses = db.query(Expense).filter(Expense.group_id == group_id).all()
    for expense in expenses:
        if expense.paid_by in balances:
            balances[expense.paid_by]["paid"] += expense.amount

        # Check if there are splits
        splits = db.query(ExpenseSplit).filter(ExpenseSplit.expense_id == expense.id).all()
        if splits:
            for split in splits:
                if split.user_id in balances:
                    balances[split.user_id]["owes"] += split.amount
        else:
            # Fallback to equal split among all current group members if no splits found
            share = expense.amount / len(members) if members else 0.0
            for member in members:
                balances[member.user_id]["owes"] += share

    # Fetch all settlements in the group
    settlements = db.query(Settlement).filter(Settlement.group_id == group_id).all()
    for settlement in settlements:
        if settlement.payer_id in balances:
            balances[settlement.payer_id]["paid"] += settlement.amount
        if settlement.receiver_id in balances:
            balances[settlement.receiver_id]["owes"] += settlement.amount

    # Compute balance = paid - owes
    for user_id in balances:
        balances[user_id]["balance"] = balances[user_id]["paid"] - balances[user_id]["owes"]

    return list(balances.values())