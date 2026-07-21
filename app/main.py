from fastapi import FastAPI
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
from app.routes import notification_routes
from app.models.notification import Notification
from app.routes.auth_routes import router as auth_router

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.include_router(auth_router)
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