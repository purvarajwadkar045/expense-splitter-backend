from datetime import datetime
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


BudgetStatus = Literal["not_set", "within_budget", "near_limit", "exceeded"]


class BudgetUpsert(BaseModel):
    month: str
    amount: float = Field(gt=0, allow_inf_nan=False)

    @field_validator("month")
    @classmethod
    def validate_month(cls, value: str) -> str:
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value):
            raise ValueError("Month must use YYYY-MM format")
        try:
            datetime.strptime(value, "%Y-%m")
        except ValueError as exc:
            raise ValueError("Month must use YYYY-MM format") from exc
        return value


class BudgetResponse(BaseModel):
    month: str
    budget: Optional[float]
    spent: float
    remaining: Optional[float]
    percentage_used: Optional[float]
    status: BudgetStatus


class InsightExpense(BaseModel):
    amount: float
    description: str
    date: datetime


class InsightCategory(BaseModel):
    category: str
    amount: float | None = None
    percentage: float | None = None
    count: int | None = None


class InsightGroup(BaseModel):
    group_id: int
    group_name: str
    amount: float


class MonthlyInsight(BaseModel):
    current: float
    previous: float
    percentage: float | None
    direction: Literal["increase", "decrease", "no_change"]


class InsightsResponse(BaseModel):
    period: str
    total_spent: float
    average_expense: float
    expense_count: int
    highest_expense: InsightExpense | None
    lowest_expense: InsightExpense | None
    top_category: InsightCategory | None
    most_frequent_category: InsightCategory | None
    top_group: InsightGroup | None
    monthly_change: MonthlyInsight
    budget: BudgetResponse | None


class HeatmapCell(BaseModel):
    day: str
    period: str
    amount: float
    count: int


class HeatmapSummary(BaseModel):
    day: str
    amount: float
    count: int


class HeatmapPeriodSummary(BaseModel):
    period: str
    amount: float
    count: int


class HeatmapSlot(BaseModel):
    day: str
    period: str
    amount: float
    count: int


class HeatmapResponse(BaseModel):
    days: list[str]
    periods: list[str]
    data: list[HeatmapCell]
    highest_day: HeatmapSummary | None
    highest_time_period: HeatmapPeriodSummary | None
    highest_period: HeatmapSlot | None


class TopExpensePayer(BaseModel):
    user_id: int
    name: str


class TopExpenseGroup(BaseModel):
    group_id: int
    name: str


class TopExpenseItem(BaseModel):
    expense_id: int
    description: str
    amount: float
    date: datetime
    category: str
    payer: TopExpensePayer
    group: TopExpenseGroup


class TopExpensesResponse(BaseModel):
    expenses: list[TopExpenseItem]
    count: int


class CategoryAnalyticsItem(BaseModel):
    category: str
    total_amount: float
    percentage: float


class CategoryAnalyticsResponse(BaseModel):
    total_spending: float
    categories: list[CategoryAnalyticsItem]
    most_expensive_category: Optional[str]


class MonthlyTrendItem(BaseModel):
    month: str
    total: float
    expense_count: int
    change_percentage: Optional[float]


class MonthlySummaryPoint(BaseModel):
    month: str
    total: float


class MonthlyTrendResponse(BaseModel):
    months: list[MonthlyTrendItem]
    peak_month: Optional[MonthlySummaryPoint]
    lowest_month: Optional[MonthlySummaryPoint]
    average_monthly_spending: float


class MemberAnalyticsItem(BaseModel):
    user_id: int
    name: str
    paid: float
    owes: float
    net: float
    expense_count: int


class MemberHighlight(BaseModel):
    user_id: int
    name: str
    amount: float | None = None
    expense_count: int | None = None


class MemberAnalyticsResponse(BaseModel):
    members: list[MemberAnalyticsItem]
    most_active_member: Optional[MemberHighlight]
    highest_payer: Optional[MemberHighlight]
    highest_debtor: Optional[MemberHighlight]


class GroupHighestExpense(BaseModel):
    expense_id: int
    description: str
    amount: float


class GroupAnalyticsItem(BaseModel):
    group_id: int
    group_name: str
    total_expenses: float
    member_count: int
    expense_count: int
    average_expense: float
    highest_expense: Optional[GroupHighestExpense]


class GroupAnalyticsResponse(BaseModel):
    groups: list[GroupAnalyticsItem]


class AnalyticsSummaryResponse(BaseModel):
    total_expenses: float
    total_groups: int
    total_transactions: int
    average_expense: float
    highest_expense: float
    lowest_expense: float
    total_settlements: float
    pending_balance: float
    my_spending: float
    i_owe: float
    i_am_owed: float