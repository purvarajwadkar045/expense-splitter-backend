from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.db.database import Base


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    creator = relationship("User", back_populates="created_groups")
    members = relationship(
        "GroupMember",
        back_populates="group",
        cascade="all, delete-orphan"
    )
    expenses = relationship(
        "Expense",
        back_populates="group",
        cascade="all, delete-orphan"
    )
    settlements = relationship(
        "Settlement",
        back_populates="group",
        cascade="all, delete-orphan"
    )