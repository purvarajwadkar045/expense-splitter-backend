from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.logging_config import setup_logging
from app.core.exceptions import register_exception_handlers

# Initialize logging system
setup_logging()

from app.routes import auth_routes
from app.routes import user_routes
from app.db.database import Base, engine
from app.models.user import User
from app.models.group import Group
from app.models.group_member import GroupMember
from app.models.expense import Expense
from app.models.settlement import Settlement
from app.routes import group_routes
from app.routes import expense_routes
# Import models
from app.models.expense_split import ExpenseSplit
from app.models.user import User
from app.routes import balance_routes
from app.routes import settlement_routes
from app.routes import dashboard_routes
from app.routes import simplify_routes
from app.routes import activity_routes
from app.models.activity import Activity
from app.models.notification import Notification
from app.models.otp import UserOTP
from sqlalchemy import text

# Dynamic database schema check/upgrade on startup
Base.metadata.create_all(bind=engine)

if "sqlite" not in str(engine.url):
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE;"))
            conn.commit()
    except Exception as e:
        import logging
        logging.getLogger("app").warning(f"Could not check/add is_verified column: {e}")

app = FastAPI()
register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_routes.router)
app.include_router(user_routes.router)
app.include_router(group_routes.router)
app.include_router(expense_routes.router)
app.include_router(expense_routes.expense_direct_router)
app.include_router(balance_routes.router)
app.include_router(settlement_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(simplify_routes.router)
app.include_router(activity_routes.router)
app.include_router(notification_routes.router)