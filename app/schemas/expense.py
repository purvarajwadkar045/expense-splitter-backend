from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Literal, Optional, List

ExpenseCategory = Literal[
    "Food",
    "Travel",
    "Hotel",
    "Shopping",
    "Bills",
    "Entertainment",
    "Fuel",
    "Rent",
    "Medical",
    "Education",
    "Other",
]

class ExpenseSplitInput(BaseModel):
    user_id: int = Field(gt=0)
    amount: float = Field(gt=0, allow_inf_nan=False)


class ExpenseCreate(BaseModel):
    title: str
    amount: float = Field(allow_inf_nan=False)
    category: ExpenseCategory = "Other"
    description: Optional[str] = None
    paid_by: Optional[int] = None
    participants: Optional[List[int]] = None
    splits: Optional[List[ExpenseSplitInput]] = None

class ExpenseResponse(BaseModel):
    id: int
    title: str
    amount: float
    category: ExpenseCategory
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
    category: ExpenseCategory
    paid_by: str
    split_type: Literal["equal", "custom"]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExpenseUpdate(BaseModel):
    title: Optional[str] = None
    amount: Optional[float] = Field(default=None, allow_inf_nan=False)
    description: Optional[str] = None
    category: Optional[ExpenseCategory] = None
    participants: Optional[List[int]] = None
    splits: Optional[List[ExpenseSplitInput]] = None


