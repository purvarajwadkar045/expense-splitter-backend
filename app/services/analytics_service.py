import csv
import io
import re
from datetime import datetime, timedelta
from math import isfinite

from fastapi import HTTPException
from sqlalchemy import Integer, exists, func, or_
from sqlalchemy.orm import Session

from app.models.expense import Expense
from app.models.expense_split import ExpenseSplit
from app.models.budget import Budget
from app.models.group import Group
from app.models.group_member import GroupMember
from app.models.settlement import Settlement
from app.models.user import User
from app.services import dashboard_service


SUPPORTED_CATEGORIES = (
    "Food",
    "Travel",
    "Hotel",
    "Shopping",
    "Bills",
    "Entertainment",
    "Fuel",
    "Rent",
    "Medical",
    "Education",
    "Other",
)

BUDGET_NEAR_LIMIT_RATIO = 0.8
SUPPORTED_DATE_RANGES = {"this-week", "this-month", "last-3-months", "this-year", "all"}

HEATMAP_DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
HEATMAP_PERIODS = ("Morning", "Afternoon", "Evening", "Night")


def get_summary(current_user: User, db: Session, **filters):
    expense_query, group_ids = build_expense_query(current_user, db, **filters)
    expenses = expense_query.all()
    total_expenses = sum(expense.amount for expense in expenses)
    expense_count = len(expenses)
    expense_amounts = [expense.amount for expense in expenses]

    settlements_total = db.query(func.sum(Settlement.amount)).filter(
        Settlement.group_id.in_(group_ids)
    ).scalar() if group_ids else None

    dashboard = dashboard_service.get_dashboard_data(current_user, db)

    return {
        "total_expenses": round(total_expenses, 2),
        "total_groups": len(group_ids),
        "total_transactions": expense_count,
        "average_expense": round(total_expenses / expense_count, 2) if expense_count else 0.0,
        "highest_expense": round(max(expense_amounts), 2) if expense_amounts else 0.0,
        "lowest_expense": round(min(expense_amounts), 2) if expense_amounts else 0.0,
        "total_settlements": round(float(settlements_total), 2) if settlements_total is not None else 0.0,
        "pending_balance": dashboard["total_you_owe"],
        "my_spending": round(sum(
            expense.amount for expense in expenses if expense.paid_by == current_user.id
        ), 2),
        "i_owe": dashboard["total_you_owe"],
        "i_am_owed": dashboard["total_owed_to_you"],
    }


def get_category_analysis(current_user: User, db: Session, **filters):
    expense_query, _ = build_expense_query(current_user, db, **filters)
    expenses = expense_query.all()
    totals = {category: 0.0 for category in SUPPORTED_CATEGORIES}
    for expense in expenses:
        category = expense.category or "Other"
        if category not in totals:
            category = "Other"
        totals[category] += expense.amount

    total_spending = sum(totals.values())
    categories = [
        {
            "category": category,
            "total_amount": round(amount, 2),
            "percentage": round((amount / total_spending) * 100, 2),
        }
        for category, amount in totals.items()
        if amount > 0
    ]
    categories.sort(key=lambda item: item["total_amount"], reverse=True)

    return {
        "total_spending": round(total_spending, 2),
        "categories": categories,
        "most_expensive_category": categories[0]["category"] if categories else None,
    }


def _month_start(value: datetime) -> datetime:
    return datetime(value.year, value.month, 1)


def _shift_month(value: datetime, months: int) -> datetime:
    month_index = value.year * 12 + value.month - 1 + months
    return datetime(month_index // 12, month_index % 12 + 1, 1)


def _parse_analytics_month(value: str) -> datetime:
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value):
        raise HTTPException(status_code=400, detail="Month must use YYYY-MM format")
    try:
        return datetime.strptime(value, "%Y-%m")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Month must use YYYY-MM format") from exc


def _date_range_start(date_range: str | None, now: datetime) -> datetime | None:
    if date_range == "this-week":
        today = datetime(now.year, now.month, now.day)
        return today - timedelta(days=today.weekday())
    if date_range == "this-month":
        return _month_start(now)
    if date_range == "last-3-months":
        return _shift_month(_month_start(now), -2)
    if date_range == "this-year":
        return datetime(now.year, 1, 1)
    return None


def build_expense_query(
    current_user: User,
    db: Session,
    *,
    search: str | None = None,
    date_range: str | None = None,
    month: str | None = None,
    group_id: int | None = None,
    category: str | None = None,
    member_id: int | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    start_date=None,
    end_date=None,
):
    if date_range is not None and date_range not in SUPPORTED_DATE_RANGES:
        raise HTTPException(status_code=400, detail="Unsupported date range")
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

    user_group_ids = [group_id_value for (group_id_value,) in db.query(GroupMember.group_id).filter(
        GroupMember.user_id == current_user.id
    ).all()]
    if group_id is not None:
        if group_id not in user_group_ids:
            raise HTTPException(status_code=403, detail="You are not a member of this group")
        group_ids = [group_id]
    else:
        group_ids = user_group_ids

    query = db.query(Expense).filter(Expense.group_id.in_(group_ids))
    if month:
        month_start = _parse_analytics_month(month)
        query = query.filter(
            Expense.created_at >= month_start,
            Expense.created_at < _shift_month(month_start, 1),
        )
    else:
        range_start = _date_range_start(date_range, datetime.utcnow())
        if range_start is not None:
            query = query.filter(Expense.created_at >= range_start)
    if start_date is not None:
        query = query.filter(Expense.created_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date is not None:
        query = query.filter(Expense.created_at <= datetime.combine(end_date, datetime.max.time()))
    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(or_(
            Expense.title.ilike(search_term),
            Expense.description.ilike(search_term),
            Expense.category.ilike(search_term),
            Expense.group.has(Group.name.ilike(search_term)),
            Expense.payer.has(User.username.ilike(search_term)),
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
    return query, group_ids


def _month_key(value) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m")
    return str(value)[:7]


def _month_index(month_key: str) -> int:
    year, month = month_key.split("-")
    return int(year) * 12 + int(month)


def get_monthly_analysis(current_user: User, db: Session, date_range: str | None = None, **filters):
    expense_query, group_ids = build_expense_query(current_user, db, date_range=date_range, **filters)
    if not group_ids:
        return {
            "months": [],
            "peak_month": None,
            "lowest_month": None,
            "average_monthly_spending": 0.0,
        }

    month_expression = (
        func.date_trunc("month", Expense.created_at)
        if db.bind.dialect.name == "postgresql"
        else func.strftime("%Y-%m", Expense.created_at)
    )
    query = expense_query.with_entities(
        month_expression.label("month"),
        func.sum(Expense.amount).label("total"),
        func.count(Expense.id).label("expense_count"),
    )

    rows = query.group_by(month_expression).order_by(month_expression).all()
    months = []
    previous_month = None
    previous_total = None
    for row in rows:
        month = _month_key(row.month)
        total = round(float(row.total), 2)
        change_percentage = None
        if (
            previous_month is not None
            and previous_total not in (None, 0)
            and _month_index(month) == _month_index(previous_month) + 1
        ):
            change_percentage = round(((total - previous_total) / previous_total) * 100, 2)
        months.append({
            "month": month,
            "total": total,
            "expense_count": int(row.expense_count),
            "change_percentage": change_percentage,
        })
        previous_month = month
        previous_total = total

    peak_month = max(months, key=lambda item: item["total"]) if months else None
    lowest_month = min(months, key=lambda item: item["total"]) if months else None
    return {
        "months": months,
        "peak_month": {
            "month": peak_month["month"],
            "total": peak_month["total"],
        } if peak_month else None,
        "lowest_month": {
            "month": lowest_month["month"],
            "total": lowest_month["total"],
        } if lowest_month else None,
        "average_monthly_spending": round(
            sum(item["total"] for item in months) / len(months), 2
        ) if months else 0.0,
    }


def get_member_analysis(
    current_user: User,
    db: Session,
    date_range: str | None = None,
    group_id: int | None = None,
    **filters,
):
    expense_query, group_ids = build_expense_query(
        current_user, db, date_range=date_range, group_id=group_id, **filters
    )

    if not group_ids:
        return {
            "members": [],
            "most_active_member": None,
            "highest_payer": None,
            "highest_debtor": None,
        }

    expenses = expense_query.all()
    if not expenses:
        return {
            "members": [],
            "most_active_member": None,
            "highest_payer": None,
            "highest_debtor": None,
        }

    member_rows = db.query(GroupMember.group_id, User.id, User.username).join(
        User, User.id == GroupMember.user_id
    ).filter(GroupMember.group_id.in_(group_ids)).all()
    member_names = {user_id: username for _, user_id, username in member_rows}
    members_by_group = {}
    for scoped_group_id, user_id, _ in member_rows:
        members_by_group.setdefault(scoped_group_id, []).append(user_id)

    metrics = {
        user_id: {"paid": 0.0, "owes": 0.0, "expense_count": 0}
        for user_id in member_names
    }
    expense_ids = [expense.id for expense in expenses]

    paid_rows = db.query(
        Expense.paid_by,
        func.sum(Expense.amount),
        func.count(Expense.id),
    ).filter(Expense.id.in_(expense_ids)).group_by(Expense.paid_by).all()
    for user_id, paid, expense_count in paid_rows:
        if user_id in metrics:
            metrics[user_id]["paid"] += float(paid)
            metrics[user_id]["expense_count"] = int(expense_count)

    split_rows = db.query(ExpenseSplit).filter(ExpenseSplit.expense_id.in_(expense_ids)).all()
    splits_by_expense = {}
    for split in split_rows:
        splits_by_expense.setdefault(split.expense_id, []).append(split)
        if split.user_id in metrics:
            metrics[split.user_id]["owes"] += split.amount

    for expense in expenses:
        if splits_by_expense.get(expense.id):
            continue
        group_members = members_by_group.get(expense.group_id, [])
        share = expense.amount / len(group_members) if group_members else 0.0
        for user_id in group_members:
            metrics[user_id]["owes"] += share

    members = []
    for user_id in sorted(metrics):
        paid = round(metrics[user_id]["paid"], 2)
        owes = round(metrics[user_id]["owes"], 2)
        members.append({
            "user_id": user_id,
            "name": member_names[user_id],
            "paid": paid,
            "owes": owes,
            "net": round(paid - owes, 2),
            "expense_count": metrics[user_id]["expense_count"],
        })

    highest_payer = max(members, key=lambda member: member["paid"])
    highest_debtor = max(members, key=lambda member: member["owes"])
    most_active = max(members, key=lambda member: member["expense_count"])
    return {
        "members": members,
        "most_active_member": {
            "user_id": most_active["user_id"],
            "name": most_active["name"],
            "expense_count": most_active["expense_count"],
        },
        "highest_payer": {
            "user_id": highest_payer["user_id"],
            "name": highest_payer["name"],
            "amount": highest_payer["paid"],
        },
        "highest_debtor": {
            "user_id": highest_debtor["user_id"],
            "name": highest_debtor["name"],
            "amount": highest_debtor["owes"],
        },
    }


def get_group_analysis(
    current_user: User,
    db: Session,
    date_range: str | None = None,
    group_id: int | None = None,
    start_date=None,
    end_date=None,
    **filters,
):
    expense_query, group_ids = build_expense_query(
        current_user,
        db,
        date_range=date_range,
        group_id=group_id,
        start_date=start_date,
        end_date=end_date,
        **filters,
    )

    if not group_ids:
        return {"groups": []}

    scoped_expenses = expense_query.all()
    expense_ids = [expense.id for expense in scoped_expenses]
    totals = db.query(
        Expense.group_id,
        func.sum(Expense.amount),
        func.count(Expense.id),
    ).filter(Expense.id.in_(expense_ids)).group_by(Expense.group_id).all() if expense_ids else []
    totals_by_group = {
        scoped_group_id: {
            "total": round(float(total), 2),
            "count": int(count),
        }
        for scoped_group_id, total, count in totals
    }

    highest_by_group = {}
    for expense in sorted(scoped_expenses, key=lambda item: (-item.amount, item.id)):
        highest_by_group.setdefault(expense.group_id, expense)

    group_rows = db.query(Group.id, Group.name).filter(Group.id.in_(group_ids)).order_by(Group.id).all()
    member_counts = dict(db.query(
        GroupMember.group_id,
        func.count(GroupMember.user_id),
    ).filter(GroupMember.group_id.in_(group_ids)).group_by(GroupMember.group_id).all())

    groups = []
    for scoped_group_id, group_name in group_rows:
        group_totals = totals_by_group.get(scoped_group_id, {"total": 0.0, "count": 0})
        highest = highest_by_group.get(scoped_group_id)
        groups.append({
            "group_id": scoped_group_id,
            "group_name": group_name,
            "total_expenses": group_totals["total"],
            "member_count": int(member_counts.get(scoped_group_id, 0)),
            "expense_count": group_totals["count"],
            "average_expense": round(
                group_totals["total"] / group_totals["count"], 2
            ) if group_totals["count"] else 0.0,
            "highest_expense": {
                "expense_id": highest.id,
                "description": highest.title,
                "amount": round(highest.amount, 2),
            } if highest else None,
        })
    return {"groups": groups}


def _validate_budget_month(month: str | None) -> str:
    value = month or datetime.utcnow().strftime("%Y-%m")
    _parse_analytics_month(value)
    return value


def _budget_month_bounds(month: str):
    start = datetime.strptime(month, "%Y-%m")
    end = _shift_month(start, 1)
    return start, end


def _get_budget_spent(current_user: User, db: Session, month: str) -> float:
    group_ids = [group_id for (group_id,) in db.query(GroupMember.group_id).filter(
        GroupMember.user_id == current_user.id
    ).all()]
    if not group_ids:
        return 0.0
    start, end = _budget_month_bounds(month)
    spent = db.query(func.sum(Expense.amount)).filter(
        Expense.group_id.in_(group_ids),
        Expense.created_at >= start,
        Expense.created_at < end,
    ).scalar()
    return round(float(spent), 2) if spent is not None else 0.0


def _build_budget_response(current_user: User, db: Session, month: str):
    budget = db.query(Budget).filter(
        Budget.user_id == current_user.id,
        Budget.budget_month == month,
    ).first()
    spent = _get_budget_spent(current_user, db, month)
    if budget is None:
        return {
            "month": month,
            "budget": None,
            "spent": spent,
            "remaining": None,
            "percentage_used": None,
            "status": "not_set",
        }

    budget_amount = round(budget.amount, 2)
    percentage_used = round((spent / budget_amount) * 100, 2)
    if percentage_used > 100:
        status = "exceeded"
    elif percentage_used >= BUDGET_NEAR_LIMIT_RATIO * 100:
        status = "near_limit"
    else:
        status = "within_budget"
    return {
        "month": month,
        "budget": budget_amount,
        "spent": spent,
        "remaining": round(budget_amount - spent, 2),
        "percentage_used": percentage_used,
        "status": status,
    }


def get_budget(current_user: User, db: Session, month: str | None = None):
    validated_month = _validate_budget_month(month)
    return _build_budget_response(current_user, db, validated_month)


def upsert_budget(current_user: User, db: Session, budget_data):
    month = _validate_budget_month(budget_data.month)
    budget = db.query(Budget).filter(
        Budget.user_id == current_user.id,
        Budget.budget_month == month,
    ).first()
    if budget is None:
        budget = Budget(
            user_id=current_user.id,
            budget_month=month,
            amount=budget_data.amount,
        )
        db.add(budget)
    else:
        budget.amount = budget_data.amount
    db.commit()
    return _build_budget_response(current_user, db, month)


def _insight_period(month: str | None, date_range: str | None):
    if month:
        start = _parse_analytics_month(month)
        return month, start, _shift_month(start, 1)

    now = datetime.utcnow()
    if date_range == "this-week":
        start = datetime(now.year, now.month, now.day) - timedelta(days=now.weekday())
        return start.strftime("%Y-%m-%d"), start, start + timedelta(days=7)
    if date_range == "last-3-months":
        start = _shift_month(_month_start(now), -2)
        return f"{start.strftime('%Y-%m')} to {now.strftime('%Y-%m')}", start, _shift_month(_month_start(now), 1)
    if date_range == "this-year":
        start = datetime(now.year, 1, 1)
        return str(now.year), start, datetime(now.year + 1, 1, 1)
    start = _month_start(now)
    return start.strftime("%Y-%m"), start, _shift_month(start, 1)


def _insight_expenses(current_user: User, db: Session, start: datetime, end: datetime, **filters):
    expense_query, group_ids = build_expense_query(current_user, db, **filters)
    expenses = expense_query.filter(
        Expense.created_at >= start,
        Expense.created_at < end,
    ).all()
    return expenses, group_ids


def get_insights(
    current_user: User,
    db: Session,
    date_range: str | None = None,
    month: str | None = None,
    **filters,
):
    period, start, end = _insight_period(month, date_range)
    current_filters = {key: value for key, value in filters.items() if value is not None}
    expenses, group_ids = _insight_expenses(current_user, db, start, end, **current_filters)

    total_spent = round(sum(expense.amount for expense in expenses), 2)
    expense_count = len(expenses)
    highest = max(expenses, key=lambda expense: (expense.amount, -expense.id), default=None)
    lowest = min(expenses, key=lambda expense: (expense.amount, expense.id), default=None)

    category_totals = {}
    category_counts = {}
    for expense in expenses:
        category = expense.category or "Other"
        category_totals[category] = category_totals.get(category, 0.0) + expense.amount
        category_counts[category] = category_counts.get(category, 0) + 1
    top_category_name = max(category_totals, key=category_totals.get, default=None)
    frequent_category_name = max(category_counts, key=category_counts.get, default=None)

    group_totals = {}
    for expense in expenses:
        group_totals[expense.group_id] = group_totals.get(expense.group_id, 0.0) + expense.amount
    group_names = dict(db.query(Group.id, Group.name).filter(Group.id.in_(group_totals)).all()) if group_totals else {}
    top_group_id = max(group_totals, key=group_totals.get, default=None)

    current_month = _month_start(start)
    previous_month = _shift_month(current_month, -1)
    previous_expenses, _ = _insight_expenses(
        current_user,
        db,
        previous_month,
        current_month,
        **{key: value for key, value in current_filters.items() if key not in {"month", "date_range"}},
    )
    previous_total = round(sum(expense.amount for expense in previous_expenses), 2)
    if previous_total == 0:
        direction = "no_change" if total_spent == 0 else "increase"
        percentage = None
    else:
        difference = round(((total_spent - previous_total) / previous_total) * 100, 2)
        direction = "increase" if difference > 0 else "decrease" if difference < 0 else "no_change"
        percentage = difference

    budget = _build_budget_response(current_user, db, current_month.strftime("%Y-%m"))
    return {
        "period": period,
        "total_spent": total_spent,
        "average_expense": round(total_spent / expense_count, 2) if expense_count else 0.0,
        "expense_count": expense_count,
        "highest_expense": {
            "amount": round(highest.amount, 2),
            "description": highest.title,
            "date": highest.created_at,
        } if highest else None,
        "lowest_expense": {
            "amount": round(lowest.amount, 2),
            "description": lowest.title,
            "date": lowest.created_at,
        } if lowest else None,
        "top_category": {
            "category": top_category_name,
            "amount": round(category_totals[top_category_name], 2),
            "percentage": round((category_totals[top_category_name] / total_spent) * 100, 2) if total_spent else None,
        } if top_category_name else None,
        "most_frequent_category": {
            "category": frequent_category_name,
            "count": category_counts[frequent_category_name],
        } if frequent_category_name else None,
        "top_group": {
            "group_id": top_group_id,
            "group_name": group_names[top_group_id],
            "amount": round(group_totals[top_group_id], 2),
        } if top_group_id else None,
        "monthly_change": {
            "current": total_spent,
            "previous": previous_total,
            "percentage": percentage,
            "direction": direction,
        },
        "budget": budget,
    }


def _heatmap_period(hour):
    if 6 <= hour < 12:
        return "Morning"
    if 12 <= hour < 17:
        return "Afternoon"
    if 17 <= hour < 21:
        return "Evening"
    return "Night"


def get_heatmap(
    current_user: User,
    db: Session,
    date_range: str | None = None,
    month: str | None = None,
    group_id: int | None = None,
    **filters,
):
    expense_query, group_ids = build_expense_query(
        current_user, db, date_range=date_range, month=month, group_id=group_id, **filters
    )

    cells = {(day, period): {"amount": 0.0, "count": 0}
             for day in HEATMAP_DAYS for period in HEATMAP_PERIODS}
    if not group_ids:
        return {
            "days": list(HEATMAP_DAYS),
            "periods": list(HEATMAP_PERIODS),
            "data": [{"day": day, "period": period, **values} for (day, period), values in cells.items()],
            "highest_day": None,
            "highest_time_period": None,
            "highest_period": None,
        }

    dialect = db.bind.dialect.name
    if dialect == "postgresql":
        day_expression = func.extract("isodow", Expense.created_at)
        hour_expression = func.extract("hour", Expense.created_at)
    else:
        # SQLite stores the same naive UTC datetimes in the test database.
        day_expression = ((func.strftime("%w", Expense.created_at).cast(Integer) + 6) % 7) + 1
        hour_expression = func.strftime("%H", Expense.created_at).cast(Integer)

    scoped_expense_ids = expense_query.with_entities(Expense.id).scalar_subquery()
    rows = db.query(
        day_expression.label("day_number"),
        hour_expression.label("hour"),
        func.sum(Expense.amount).label("amount"),
        func.count(Expense.id).label("count"),
    ).filter(Expense.id.in_(scoped_expense_ids)).group_by(
        day_expression, hour_expression
    ).all()

    for row in rows:
        day_number = int(row.day_number)
        day = HEATMAP_DAYS[day_number - 1]
        period = _heatmap_period(int(row.hour))
        cells[(day, period)]["amount"] += float(row.amount)
        cells[(day, period)]["count"] += int(row.count)

    data = [
        {
            "day": day,
            "period": period,
            "amount": round(values["amount"], 2),
            "count": values["count"],
        }
        for (day, period), values in cells.items()
    ]
    day_totals = {
        day: {
            "day": day,
            "amount": round(sum(cell["amount"] for cell in data if cell["day"] == day), 2),
            "count": sum(cell["count"] for cell in data if cell["day"] == day),
        }
        for day in HEATMAP_DAYS
    }
    period_totals = {
        period: {
            "period": period,
            "amount": round(sum(cell["amount"] for cell in data if cell["period"] == period), 2),
            "count": sum(cell["count"] for cell in data if cell["period"] == period),
        }
        for period in HEATMAP_PERIODS
    }
    highest_cell = max(data, key=lambda cell: cell["amount"], default=None)
    return {
        "days": list(HEATMAP_DAYS),
        "periods": list(HEATMAP_PERIODS),
        "data": data,
        "highest_day": max(day_totals.values(), key=lambda item: item["amount"]) if any(item["amount"] for item in day_totals.values()) else None,
        "highest_time_period": max(period_totals.values(), key=lambda item: item["amount"]) if any(item["amount"] for item in period_totals.values()) else None,
        "highest_period": highest_cell if highest_cell and highest_cell["amount"] > 0 else None,
    }


def get_top_expenses(
    current_user: User,
    db: Session,
    limit: int = 10,
    date_range: str | None = None,
    month: str | None = None,
    group_id: int | None = None,
    category: str | None = None,
    **filters,
):
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 50")
    query, group_ids = build_expense_query(
        current_user,
        db,
        date_range=date_range,
        month=month,
        group_id=group_id,
        category=category,
        **filters,
    )
    if not group_ids:
        return {"expenses": [], "count": 0}

    expenses = query.order_by(
        Expense.amount.desc(),
        Expense.created_at.desc(),
        Expense.id.desc(),
    ).limit(limit).all()
    group_names = dict(db.query(Group.id, Group.name).filter(
        Group.id.in_({expense.group_id for expense in expenses})
    ).all()) if expenses else {}
    payer_names = dict(db.query(User.id, User.username).filter(
        User.id.in_({expense.paid_by for expense in expenses})
    ).all()) if expenses else {}

    return {
        "expenses": [
            {
                "expense_id": expense.id,
                "description": expense.title,
                "amount": round(expense.amount, 2),
                "date": expense.created_at,
                "category": expense.category or "Other",
                "payer": {"user_id": expense.paid_by, "name": payer_names.get(expense.paid_by, "Unknown")},
                "group": {"group_id": expense.group_id, "name": group_names.get(expense.group_id, "Unknown")},
            }
            for expense in expenses
        ],
        "count": len(expenses),
    }


def export_csv(
    current_user: User,
    db: Session,
    report: str,
    **filters,
):
    output = io.StringIO(newline="")
    writer = csv.writer(output)

    if report == "expenses":
        query, _ = build_expense_query(current_user, db, **filters)
        expenses = query.order_by(Expense.created_at.desc(), Expense.id.desc()).all()
        writer.writerow(["Expense ID", "Description", "Amount", "Category", "Date", "Payer", "Group", "Created At"])
        group_names = dict(db.query(Group.id, Group.name).filter(
            Group.id.in_({expense.group_id for expense in expenses})
        ).all()) if expenses else {}
        payer_names = dict(db.query(User.id, User.username).filter(
            User.id.in_({expense.paid_by for expense in expenses})
        ).all()) if expenses else {}
        for expense in expenses:
            writer.writerow([
                expense.id,
                expense.title,
                round(expense.amount, 2),
                expense.category or "Other",
                expense.created_at.date().isoformat(),
                payer_names.get(expense.paid_by, "Unknown"),
                group_names.get(expense.group_id, "Unknown"),
                expense.created_at.isoformat(),
            ])
    elif report == "summary":
        summary = get_summary(current_user, db, **filters)
        writer.writerow(["Metric", "Value"])
        for label, key in [
            ("Total Expenses", "total_expenses"),
            ("Expense Count", "total_transactions"),
            ("Average Expense", "average_expense"),
            ("Highest Expense", "highest_expense"),
            ("Lowest Expense", "lowest_expense"),
            ("Total Settlements", "total_settlements"),
            ("Pending Balance", "pending_balance"),
        ]:
            writer.writerow([label, summary[key]])
    elif report == "category":
        result = get_category_analysis(current_user, db, **filters)
        writer.writerow(["Category", "Amount", "Percentage", "Expense Count"])
        query, _ = build_expense_query(current_user, db, **filters)
        counts = dict(query.with_entities(Expense.category, func.count(Expense.id)).group_by(Expense.category).all())
        for item in result["categories"]:
            writer.writerow([item["category"], item["total_amount"], item["percentage"], counts.get(item["category"], 0)])
    elif report == "monthly":
        result = get_monthly_analysis(current_user, db, filters.pop("date_range", None), **filters)
        writer.writerow(["Month", "Amount", "Expense Count", "Change Percentage"])
        for item in result["months"]:
            writer.writerow([item["month"], item["total"], item["expense_count"], item["change_percentage"]])
    elif report == "member":
        result = get_member_analysis(
            current_user,
            db,
            filters.pop("date_range", None),
            filters.pop("group_id", None),
            **filters,
        )
        writer.writerow(["Member", "Paid", "Owes", "Net", "Expense Count"])
        for member in result["members"]:
            writer.writerow([member["name"], member["paid"], member["owes"], member["net"], member["expense_count"]])
    else:
        raise HTTPException(status_code=400, detail="Unsupported report type")

    return output.getvalue()