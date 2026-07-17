from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException
from app.models.activity import Activity
from app.services.authorization import check_group_membership


def log_activity(db: Session, group_id: int, user_id: int, activity_type: str, message: str) -> Activity:
    activity = Activity(
        group_id=group_id,
        user_id=user_id,
        activity_type=activity_type,
        message=message
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


def get_group_activities(group_id: int, current_user, db: Session, page: int = 1, limit: int = 10):
    # 1. Verify group exists and current user belongs to the group
    check_group_membership(db, group_id, current_user.id)

    # 2. Validate page and limit values
    if page <= 0:
        raise HTTPException(status_code=400, detail="Page must be greater than 0")
    if limit <= 0:
        raise HTTPException(status_code=400, detail="Limit must be greater than 0")

    # 3. Retrieve activities ordered by newest first with pagination
    offset = (page - 1) * limit
    activities = (
        db.query(Activity)
        .options(joinedload(Activity.user))
        .filter(Activity.group_id == group_id)
        .order_by(Activity.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        {
            "id": act.id,
            "activity_type": act.activity_type,
            "message": act.message,
            "username": act.user.username if act.user else "Unknown",
            "created_at": act.created_at
        }
        for act in activities
    ]
