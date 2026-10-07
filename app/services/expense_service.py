from datetime import datetime, timedelta
from math import isclose, isfinite
from typing import Optional
from fastapi import HTTPException
from sqlalchemy import exists, func, or_
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

    # Determine who paid — default to the logged-in user
    payer_id = current_user.id
    if expense_data.paid_by is not None and expense_data.paid_by != current_user.id:
        # Verify the requested payer is a member of the group
        payer_member = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == expense_data.paid_by
        ).first()
        if not payer_member:
            raise HTTPException(
                status_code=400,
                detail=f"User {expense_data.paid_by} is not a member of this group"
            )
        payer_id = expense_data.paid_by

    if expense_data.splits is not None:
        split_values = [
            split.model_dump() if hasattr(split, "model_dump") else split
            for split in expense_data.splits
        ]
        if not split_values:
            raise HTTPException(status_code=400, detail="Participants list cannot be empty")
        participant_ids = [split["user_id"] for split in split_values]
        if len(participant_ids) != len(set(participant_ids)):
            raise HTTPException(status_code=400, detail="Duplicate participants found")
        if any(split["amount"] <= 0 for split in split_values):
            raise HTTPException(status_code=400, detail="Split amounts must be greater than zero")
        if not isclose(sum(split["amount"] for split in split_values), expense_data.amount, rel_tol=0, abs_tol=1e-9):
            raise HTTPException(status_code=400, detail="Sum of split amounts must equal expense amount")
        participants = participant_ids
        splits_by_user = {split["user_id"]: split["amount"] for split in split_values}
    elif expense_data.participants is not None:
        participants = expense_data.participants
        if not participants:
            raise HTTPException(status_code=400, detail="Participants list cannot be empty")
        if len(participants) != len(set(participants)):
            raise HTTPException(status_code=400, detail="Duplicate participants found")
        splits_by_user = None
    else:
        members = db.query(GroupMember).filter(GroupMember.group_id == group_id).all()
        participants = [member.user_id for member in members]
        if not participants:
            raise HTTPException(status_code=400, detail="Participants list cannot be empty")
        splits_by_user = None

    for participant_id in participants:
        member = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == participant_id,
        ).first()
        if not member:
            raise HTTPException(status_code=400, detail=f"User {participant_id} is not a member of this group")

    expense = Expense(
        title=expense_data.title,
        amount=expense_data.amount,
        category=expense_data.category,
        description=expense_data.description,
        group_id=group_id,
        paid_by=payer_id
    )
    db.add(expense)
    db.flush()

    if splits_by_user is not None:
        for participant_id, amount in splits_by_user.items():
            db.add(ExpenseSplit(expense_id=expense.id, user_id=participant_id, amount=amount))
    else:
        share = expense_data.amount / len(participants)
        for participant_id in participants:
            db.add(ExpenseSplit(expense_id=expense.id, user_id=participant_id, amount=share))

    db.commit()
    db.refresh(expense)
    
    from app.services.activity_service import log_activity
    amount_str = f"₹{int(expense.amount)}" if expense.amount.is_integer() else f"₹{expense.amount:.2f}"
    log_activity(db, group_id, current_user.id, "EXPENSE_CREATED", f"{current_user.username} added an expense '{expense.title}' of {amount_str}")

    # Log Notification to other group members
    group = db.query(Group).filter(Group.id == group_id).first()
    group_name = group.name if group else "Unknown Group"
    members = db.query(GroupMember).filter(GroupMember.group_id == group_id).all()
    from app.services.notification_service import create_notification
    for member in members:
        if member.user_id != current_user.id:
            create_notification(
                db,
                user_id=member.user_id,
                title="Expense Added",
                message=f"{current_user.username} added a new expense in {group_name}."
            )

    return expense


def get_group_expenses(
    group_id: int,
    current_user,
    db: Session,
    user_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    date_range: Optional[str] = None,
    search: Optional[str] = None,
    category: Optional[str] = None,
    member_id: Optional[int] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    page: int = 1,
    limit: int = 10
):
    # Validate page and limit values
    if page <= 0:
        raise HTTPException(status_code=400, detail="Page must be greater than 0")
    if limit <= 0:
        raise HTTPException(status_code=400, detail="Limit must be greater than 0")
    if min_amount is not None and min_amount < 0:
        raise HTTPException(status_code=400, detail="Minimum amount cannot be negative")
    if max_amount is not None and max_amount < 0:
        raise HTTPException(status_code=400, detail="Maximum amount cannot be negative")
    if min_amount is not None and not isfinite(min_amount):
        raise HTTPException(status_code=400, detail="Minimum amount must be finite")
    if max_amount is not None and not isfinite(max_amount):
        raise HTTPException(status_code=400, detail="Maximum amount must be finite")
    if min_amount is not None and max_amount is not None and min_amount > max_amount:
        raise HTTPException(status_code=400, detail="Minimum amount cannot exceed maximum amount")

    # Verify group exists and current user is a member
    check_group_membership(db, group_id, current_user.id)

    # Build Query with filters
    query = (
        db.query(Expense)
        .options(joinedload(Expense.payer), joinedload(Expense.splits))
        .filter(Expense.group_id == group_id)
    )

    if user_id is not None:
        query = query.filter(Expense.paid_by == user_id)
    if start_date is not None:
        query = query.filter(Expense.created_at >= start_date)
    if end_date is not None:
        query = query.filter(Expense.created_at <= end_date)
    if date_range:
        now = datetime.utcnow()
        if date_range == "this-week":
            query = query.filter(Expense.created_at >= now - timedelta(days=now.weekday()))
        elif date_range == "this-month":
            query = query.filter(Expense.created_at >= datetime(now.year, now.month, 1))
        elif date_range == "last-3-months":
            month_index = now.year * 12 + now.month - 1 - 2
            range_start = datetime(month_index // 12, month_index % 12 + 1, 1)
            query = query.filter(Expense.created_at >= range_start)
        elif date_range == "this-year":
            query = query.filter(Expense.created_at >= datetime(now.year, 1, 1))
        elif date_range != "all":
            raise HTTPException(status_code=400, detail="Unsupported date range")
    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(or_(
            Expense.title.ilike(search_term),
            Expense.description.ilike(search_term),
            Expense.category.ilike(search_term),
        ))
    if category and category.lower() != "all":
        query = query.filter(func.lower(Expense.category) == category.lower())
    if member_id is not None:
        query = query.filter(or_(
            Expense.paid_by == member_id,
            exists().where(
                ExpenseSplit.expense_id == Expense.id,
                ExpenseSplit.user_id == member_id,
            ),
        ))
    if min_amount is not None:
        query = query.filter(Expense.amount >= min_amount)
    if max_amount is not None:
        query = query.filter(Expense.amount <= max_amount)

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
            "category": exp.category or "Other",
            "paid_by": exp.payer.username if exp.payer else "Unknown",
            "split_type": "custom" if exp.splits and any(
                not isclose(split.amount, exp.splits[0].amount, rel_tol=0, abs_tol=1e-9)
                for split in exp.splits[1:]
            ) else "equal",
            "created_at": exp.created_at
        }
        for exp in expenses
    ]


def update_expense(expense_id: int, expense_data, current_user, db: Session):
    # 1. Validate that the expense exists
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    # Require both group membership and payer ownership for expense mutations.
    check_group_membership(db, expense.group_id, current_user.id)
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
    if expense_data.category is not None:
        expense.category = expense_data.category

    # Fetch old participants list before deleting the splits
    old_splits = db.query(ExpenseSplit).filter(ExpenseSplit.expense_id == expense.id).all()
    old_participant_ids = [split.user_id for split in old_splits]

    # 5. Remove old ExpenseSplit records
    db.query(ExpenseSplit).filter(ExpenseSplit.expense_id == expense.id).delete()

    # 6. Recalculate and recreate ExpenseSplit records
    if expense_data.splits is not None:
        split_values = [
            split.model_dump() if hasattr(split, "model_dump") else split
            for split in expense_data.splits
        ]
        if not split_values:
            raise HTTPException(status_code=400, detail="Participants list cannot be empty")
        participant_ids = [split["user_id"] for split in split_values]
        if len(participant_ids) != len(set(participant_ids)):
            raise HTTPException(status_code=400, detail="Duplicate participants found")
        if any(split["amount"] <= 0 for split in split_values):
            raise HTTPException(status_code=400, detail="Split amounts must be greater than zero")
        if not isclose(sum(split["amount"] for split in split_values), expense.amount, rel_tol=0, abs_tol=1e-9):
            raise HTTPException(status_code=400, detail="Sum of split amounts must equal expense amount")
        participants = participant_ids
    elif expense_data.participants is not None:
        participants = expense_data.participants
        if not participants:
            raise HTTPException(status_code=400, detail="Participants list cannot be empty")
        if len(participants) != len(set(participants)):
            raise HTTPException(status_code=400, detail="Duplicate participants found")
        if any(share <= 0 for share in [expense.amount / len(participants)]):
            raise HTTPException(status_code=400, detail="Split amounts must be greater than zero")
    else:
        # If participants list is not provided:
        if old_participant_ids:
            participants = old_participant_ids
        else:
            # Fallback to all group members
            members = db.query(GroupMember).filter(GroupMember.group_id == expense.group_id).all()
            participants = [m.user_id for m in members]

    for p_id in participants:
        member = db.query(GroupMember).filter(
            GroupMember.group_id == expense.group_id,
            GroupMember.user_id == p_id
        ).first()
        if not member:
            raise HTTPException(status_code=400, detail=f"User {p_id} is not a member of this group")

    if expense_data.splits is not None:
        splits_by_user = {split["user_id"]: split["amount"] for split in split_values}
        for p_id, amount in splits_by_user.items():
            db.add(ExpenseSplit(expense_id=expense.id, user_id=p_id, amount=amount))
    elif participants:
        share = expense.amount / len(participants)
        for p_id in participants:
            db.add(ExpenseSplit(expense_id=expense.id, user_id=p_id, amount=share))

    db.commit()
    db.refresh(expense)

    from app.services.activity_service import log_activity
    amount_str = f"₹{int(expense.amount)}" if expense.amount.is_integer() else f"₹{expense.amount:.2f}"
    log_activity(db, expense.group_id, current_user.id, "EXPENSE_UPDATED", f"{current_user.username} updated the expense '{expense.title}' to {amount_str}")

    # Log Notification to other group members
    group = db.query(Group).filter(Group.id == expense.group_id).first()
    group_name = group.name if group else "Unknown Group"
    members = db.query(GroupMember).filter(GroupMember.group_id == expense.group_id).all()
    from app.services.notification_service import create_notification
    for member in members:
        if member.user_id != current_user.id:
            create_notification(
                db,
                user_id=member.user_id,
                title="Expense Updated",
                message=f"{current_user.username} updated the expense '{expense.title}' in {group_name}."
            )

    return expense


def delete_expense(expense_id: int, current_user, db: Session):
    # 1. Validate that the expense exists
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    # Require both group membership and payer ownership for expense mutations.
    check_group_membership(db, expense.group_id, current_user.id)
    if expense.paid_by != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied")

    # Save fields before deletion
    group_id = expense.group_id
    expense_title = expense.title

    # 3. Delete associated ExpenseSplit records first
    db.query(ExpenseSplit).filter(ExpenseSplit.expense_id == expense.id).delete()

    # 4. Delete the Expense
    db.delete(expense)
    db.commit()

    from app.services.activity_service import log_activity
    log_activity(db, group_id, current_user.id, "EXPENSE_DELETED", f"{current_user.username} deleted the expense '{expense_title}'")

    # Log Notification to other group members
    group = db.query(Group).filter(Group.id == group_id).first()
    group_name = group.name if group else "Unknown Group"
    members = db.query(GroupMember).filter(GroupMember.group_id == group_id).all()
    from app.services.notification_service import create_notification
    for member in members:
        if member.user_id != current_user.id:
            create_notification(
                db,
                user_id=member.user_id,
                title="Expense Deleted",
                message=f"{current_user.username} deleted the expense '{expense_title}' in {group_name}."
            )

