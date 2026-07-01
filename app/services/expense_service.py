from fastapi import HTTPException
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
