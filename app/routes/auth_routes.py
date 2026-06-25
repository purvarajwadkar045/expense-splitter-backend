from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.dependencies.db import get_db
from app.schemas.user import (
    UserCreate,
    UserResponse
)
from app.services.auth_services import register_user

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


@router.post(
    "/register",
    response_model=UserResponse
)
def register(
    user: UserCreate,
    db: Session = Depends(get_db)
):
    created_user = register_user(
        db,
        user
    )

    if not created_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    return created_user