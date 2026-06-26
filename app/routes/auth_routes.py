from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.schemas.user import UserCreate, UserResponse
from app.services.auth_services import register_user
from app.dependencies.db import get_db

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

    new_user = register_user(user, db)

    if new_user is None:
        raise HTTPException(
            status_code=400,
            detail="Email already exists"
        )

    return new_user