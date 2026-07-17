from pydantic import BaseModel, ConfigDict
from datetime import datetime


class ActivityResponse(BaseModel):
    id: int
    activity_type: str
    message: str
    username: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
