from fastapi import FastAPI

from app.db.database import Base, engine

# Import models
from app.models.user import User

from app.routes.auth_routes import router as auth_router

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.include_router(auth_router)