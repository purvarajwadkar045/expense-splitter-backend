from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class ExpenseCreate(BaseModel):
    title: str
    amount: float
    description: Optional[str] = None

class ExpenseResponse(BaseModel):
    id: int
    title: str
    amount: float
    description: Optional[str]
    group_id: int
    paid_by: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExpenseHistoryResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    amount: float
    paid_by: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

