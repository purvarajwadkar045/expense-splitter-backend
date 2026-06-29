from fastapi import FastAPI
from app.routes import auth_routes
from app.routes import user_routes
from app.db.database import Base, engine
from app.models.user import User
from app.models.group import Group
from app.models.group_member import GroupMember
# Import models
from app.models.user import User

from app.routes.auth_routes import router as auth_router

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.include_router(auth_router)
app.include_router(auth_routes.router)
app.include_router(user_routes.router)