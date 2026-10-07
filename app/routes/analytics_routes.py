from datetime import date, datetime

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.dependencies.db import get_db
from app.models.user import User
from app.schemas.analytics import (
    AnalyticsSummaryResponse,
    CategoryAnalyticsResponse,
    MemberAnalyticsResponse,
    MonthlyTrendResponse,
    GroupAnalyticsResponse,
    BudgetResponse,
    BudgetUpsert,
    InsightsResponse,
    HeatmapResponse,
    TopExpensesResponse,
)
from app.services import analytics_service


router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/summary", response_model=AnalyticsSummaryResponse)
def get_summary(
    search: str | None = None,
    date_range: str | None = None,
    month: str | None = None,
    group_id: int | None = None,
    category: str | None = None,
    member_id: int | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return analytics_service.get_summary(current_user, db, search=search, date_range=date_range, month=month, group_id=group_id, category=category, member_id=member_id, min_amount=min_amount, max_amount=max_amount)


@router.get("/categories", response_model=CategoryAnalyticsResponse)
def get_categories(
    search: str | None = None,
    date_range: str | None = None,
    month: str | None = None,
    group_id: int | None = None,
    category: str | None = None,
    member_id: int | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return analytics_service.get_category_analysis(current_user, db, search=search, date_range=date_range, month=month, group_id=group_id, category=category, member_id=member_id, min_amount=min_amount, max_amount=max_amount)


@router.get("/monthly", response_model=MonthlyTrendResponse)
def get_monthly(
    date_range: str | None = None,
    search: str | None = None,
    month: str | None = None,
    group_id: int | None = None,
    category: str | None = None,
    member_id: int | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return analytics_service.get_monthly_analysis(current_user, db, date_range, search=search, month=month, group_id=group_id, category=category, member_id=member_id, min_amount=min_amount, max_amount=max_amount)


@router.get("/members", response_model=MemberAnalyticsResponse)
def get_members(
    date_range: str | None = None,
    group_id: int | None = None,
    search: str | None = None,
    month: str | None = None,
    category: str | None = None,
    member_id: int | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return analytics_service.get_member_analysis(current_user, db, date_range, group_id, search=search, month=month, category=category, member_id=member_id, min_amount=min_amount, max_amount=max_amount)


@router.get("/groups", response_model=GroupAnalyticsResponse)
def get_groups(
    date_range: str | None = None,
    group_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    search: str | None = None,
    month: str | None = None,
    category: str | None = None,
    member_id: int | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return analytics_service.get_group_analysis(
        current_user,
        db,
        date_range,
        group_id,
        start_date,
        end_date,
        search=search,
        month=month,
        category=category,
        member_id=member_id,
        min_amount=min_amount,
        max_amount=max_amount,
    )


@router.get("/budget", response_model=BudgetResponse)
def get_budget(
    month: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return analytics_service.get_budget(current_user, db, month)


@router.put("/budget", response_model=BudgetResponse)
def upsert_budget(
    budget_data: BudgetUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return analytics_service.upsert_budget(current_user, db, budget_data)


@router.get("/insights", response_model=InsightsResponse)
def get_insights(
    date_range: str | None = None,
    month: str | None = None,
    search: str | None = None,
    group_id: int | None = None,
    category: str | None = None,
    member_id: int | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return analytics_service.get_insights(current_user, db, date_range, month, search=search, group_id=group_id, category=category, member_id=member_id, min_amount=min_amount, max_amount=max_amount)


@router.get("/heatmap", response_model=HeatmapResponse)
def get_heatmap(
    date_range: str | None = None,
    month: str | None = None,
    group_id: int | None = None,
    search: str | None = None,
    category: str | None = None,
    member_id: int | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return analytics_service.get_heatmap(current_user, db, date_range, month, group_id, search=search, category=category, member_id=member_id, min_amount=min_amount, max_amount=max_amount)


@router.get("/top-expenses", response_model=TopExpensesResponse)
def get_top_expenses(
    limit: int = 10,
    date_range: str | None = None,
    month: str | None = None,
    group_id: int | None = None,
    category: str | None = None,
    search: str | None = None,
    member_id: int | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return analytics_service.get_top_expenses(
        current_user,
        db,
        limit,
        date_range,
        month,
        group_id,
        category,
        search=search,
        member_id=member_id,
        min_amount=min_amount,
        max_amount=max_amount,
    )


@router.get("/export")
def export_report(
    report: str = "expenses",
    format: str = "csv",
    search: str | None = None,
    date_range: str | None = None,
    month: str | None = None,
    group_id: int | None = None,
    category: str | None = None,
    member_id: int | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if format.lower() != "csv":
        return Response(
            content="Only CSV export is currently supported.",
            status_code=400,
            media_type="text/plain",
        )
    content = analytics_service.export_csv(
        current_user,
        db,
        report,
        search=search,
        date_range=date_range,
        month=month,
        group_id=group_id,
        category=category,
        member_id=member_id,
        min_amount=min_amount,
        max_amount=max_amount,
    )
    period = month or datetime.utcnow().strftime("%Y-%m")
    filename = f"{report}_report_{period}.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )