import logging
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserCreate, UserLogin
from app.core.security import hash_password, verify_password, create_access_token

logger = logging.getLogger("app")


def register_user(user: UserCreate, db: Session):

    existing_user = db.query(User).filter(
        User.email == user.email
    ).first()

    if existing_user:
        return None

    new_user = User(
        username=user.username,
        email=user.email,
        password_hash=hash_password(user.password)
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


def login_user(login_data: UserLogin, db: Session):
    user = db.query(User).filter(User.email == login_data.email).first()
    if not user:
        logger.warning(
            "Login attempt failed: user not found",
            extra={"extra_info": {"email": login_data.email}}
        )
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    if not verify_password(login_data.password, user.password_hash):
        logger.warning(
            "Login attempt failed: incorrect password",
            extra={"extra_info": {"email": login_data.email, "user_id": user.id}}
        )
        raise HTTPException(
            status_code=401,
            detail="Incorrect password"
        )

    access_token = create_access_token(
        {
            "sub": user.email
        }
    )
    logger.info(
        "Login attempt successful",
        extra={"extra_info": {"email": user.email, "user_id": user.id}}
    )
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }