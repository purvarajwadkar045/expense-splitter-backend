from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class AddMember(BaseModel):
    email: str

class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None

class GroupResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    created_by: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)