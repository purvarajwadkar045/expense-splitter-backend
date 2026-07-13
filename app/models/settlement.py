from datetime import datetime
from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base

class Settlement(Base):
    __tablename__ = "settlements"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    payer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Float, nullable=False)
    settled_at = Column(DateTime, default=datetime.utcnow)

    group = relationship("Group", back_populates="settlements")
    payer = relationship("User", foreign_keys=[payer_id], back_populates="settlements_paid")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="settlements_received")
