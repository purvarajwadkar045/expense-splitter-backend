from sqlalchemy import Column,Integer,String,Boolean
from app.db.database import Base

class User(Base):
    __tablename__="users"
    id=Column(Integer,primary_key=True)
    name=Column(String,index=True)
    email=Column(String,unique=True,nullable=False)
    password=Column(String)
    is_verified=Column(Boolean,default=False)