from pydantic import BaseModel, ConfigDict
from datetime import datetime

class SettlementCreate(BaseModel):
    payer_id: int
    receiver_id: int
    amount: float

class SettlementResponse(BaseModel):
    id: int
    group_id: int
    payer_id: int
    receiver_id: int
    amount: float
    settled_at: datetime

    model_config = ConfigDict(from_attributes=True)
