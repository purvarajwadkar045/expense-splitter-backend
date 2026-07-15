from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.user import User
from app.models.group_member import GroupMember
from app.models.expense import Expense
from app.models.expense_split import ExpenseSplit
from app.models.settlement import Settlement

def get_dashboard_data(current_user: User, db: Session):
    # 1. total_groups
    group_memberships = db.query(GroupMember).filter(GroupMember.user_id == current_user.id).all()
    group_ids = [m.group_id for m in group_memberships]
    total_groups = len(group_ids)

    # 2. total_expenses_paid
    total_expenses_paid_query = db.query(func.sum(Expense.amount)).filter(Expense.paid_by == current_user.id).scalar()
    total_expenses_paid = float(total_expenses_paid_query) if total_expenses_paid_query is not None else 0.0

    # 3. Calculate you_owe and owed_to_you per group
    total_you_owe = 0.0
    total_owed_to_you = 0.0

    for group_id in group_ids:
        # Get members count/list for equal split fallback
        members = db.query(GroupMember).filter(GroupMember.group_id == group_id).all()
        num_members = len(members)

        # Get all expenses in the group
        expenses = db.query(Expense).filter(Expense.group_id == group_id).all()
        expense_ids = [e.id for e in expenses]

        # Get all splits for these expenses
        splits = db.query(ExpenseSplit).filter(ExpenseSplit.expense_id.in_(expense_ids)).all() if expense_ids else []

        # Map splits by expense_id
        splits_by_expense = {}
        for s in splits:
            splits_by_expense.setdefault(s.expense_id, []).append(s)

        group_paid = 0.0
        group_owes = 0.0

        # Sum paid expenses in this group
        for expense in expenses:
            if expense.paid_by == current_user.id:
                group_paid += expense.amount

            # Calculate how much user owes for this expense
            expense_splits = splits_by_expense.get(expense.id, [])
            if expense_splits:
                # Custom split exists
                user_split = next((s for s in expense_splits if s.user_id == current_user.id), None)
                if user_split:
                    group_owes += user_split.amount
            else:
                # Fallback to equal split among all current group members
                share = expense.amount / num_members if num_members > 0 else 0.0
                group_owes += share

        # Sum settlements in this group
        # Settlements paid by the user (decreases net debt / increases what they paid)
        settlements_paid = db.query(func.sum(Settlement.amount)).filter(
            Settlement.group_id == group_id,
            Settlement.payer_id == current_user.id
        ).scalar()
        if settlements_paid:
            group_paid += float(settlements_paid)

        # Settlements received by the user (decreases what they are owed / increases what they owe)
        settlements_received = db.query(func.sum(Settlement.amount)).filter(
            Settlement.group_id == group_id,
            Settlement.receiver_id == current_user.id
        ).scalar()
        if settlements_received:
            group_owes += float(settlements_received)

        group_balance = group_paid - group_owes
        if group_balance > 0:
            total_owed_to_you += group_balance
        elif group_balance < 0:
            total_you_owe += abs(group_balance)

    # Net balance
    net_balance = total_owed_to_you - total_you_owe

    # Round all decimal outputs to 2 decimal places
    return {
        "user_id": current_user.id,
        "username": current_user.username,
        "total_groups": total_groups,
        "total_expenses_paid": round(total_expenses_paid, 2),
        "total_you_owe": round(total_you_owe, 2),
        "total_owed_to_you": round(total_owed_to_you, 2),
        "net_balance": round(net_balance, 2)
    }
