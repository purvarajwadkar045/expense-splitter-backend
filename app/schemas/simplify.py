from pydantic import BaseModel, ConfigDict

class SimplifyTransaction(BaseModel):
    from_user_id: int
    from_username: str
    to_user_id: int
    to_username: str
    amount: float

    model_config = ConfigDict(from_attributes=True)
