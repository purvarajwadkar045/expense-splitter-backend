from pydantic import BaseModel
from typing import Optional, List

class EqualExpenseCreate(BaseModel):
    title: str
    amount: float
    description: Optional[str] = None
    participants: List[int]
