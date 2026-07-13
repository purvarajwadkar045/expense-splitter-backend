from sqlalchemy import Column
from sqlalchemy.orm import relationship
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import DateTime

from datetime import datetime

from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    username = Column(
        String,
        nullable=False
    )

    email = Column(
        String,
        unique=True,
        nullable=False
    )

    password_hash = Column(
        String,
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )
    created_groups = relationship(
    "Group",
    back_populates="creator"
    )

    group_memberships = relationship(
    "GroupMember",
    back_populates="user",
    cascade="all, delete-orphan"
    )
    expenses_paid = relationship(
        "Expense",
        back_populates="payer"
    )
    expense_splits = relationship(
    "ExpenseSplit",
    back_populates="user",
    cascade="all, delete-orphan"
    )
    settlements_paid = relationship(
        "Settlement",
        foreign_keys="[Settlement.payer_id]",
        back_populates="payer",
        cascade="all, delete-orphan"
    )
    settlements_received = relationship(
        "Settlement",
        foreign_keys="[Settlement.receiver_id]",
        back_populates="receiver",
        cascade="all, delete-orphan"
    )