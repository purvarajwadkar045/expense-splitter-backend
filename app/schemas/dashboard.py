from pydantic import BaseModel, ConfigDict

class DashboardResponse(BaseModel):
    user_id: int
    username: str
    total_groups: int
    total_expenses_paid: float
    total_you_owe: float
    total_owed_to_you: float
    net_balance: float

    model_config = ConfigDict(from_attributes=True)
