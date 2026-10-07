from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime

class SettlementCreate(BaseModel):
    payer_id: int
    receiver_id: int
    amount: float = Field(allow_inf_nan=False)

class SettlementResponse(BaseModel):
    id: int
    group_id: int
    payer_id: int
    receiver_id: int
    amount: float
    settled_at: datetime

    model_config = ConfigDict(from_attributes=True)
