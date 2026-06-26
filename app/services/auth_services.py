from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserCreate
from app.core.security import hash_password


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