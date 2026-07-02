from sqlalchemy import Column,Integer,Float,ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base

class ExpenseSplit(Base):
    __tablename__="expense_splits"

    id=Column(
        Integer,
        primary_key=True,
        index=True
    )
    expense_id=Column(
        Integer,
        ForeignKey("expenses.id",ondelete="CASCADE"),
        nullable=False
    )
    user_id=Column(
        Integer,
        ForeignKey("users.id",ondelete="CASCADE"),
        nullable=False
    )
    amount=Column(
        Float,
        nullable=False
    )
    expense=relationship(
        "Expense",
        back_populates="splits"
    )
    user=relationship(
        "User",
        back_populates="expense_splits"
    )
   
