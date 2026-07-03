from pydantic import BaseModel, ConfigDict

class BalanceResponse(BaseModel):
    user_id:int
    username:str
    paid:float
    owes:float
    balance:float

    model_config = ConfigDict(from_attributes=True)

