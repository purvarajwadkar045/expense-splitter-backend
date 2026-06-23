from datetime import datetime
from sqlalchemy import Column,Integer,String,Boolean,DateTime
from app.db.database import Base

class OTP(Base):
    __tablename__="otp"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, index=True)
    otp_code = Column(String, nullable=False)
    expiry_time = Column(DateTime, nullable=False)
    created_at=Column(DateTime,default=datetime.utcnow)
    purpose=Column(String)
    