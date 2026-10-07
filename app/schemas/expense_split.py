from pydantic import BaseModel,ConfigDict

class EqualExpenseCreate(BaseModel):
    title:str
    amount:float
    description:str|None=None
    participants=list[int]

class ExpenseSplitResponse(BaseModel):
    id:int
    expense_id:int
    user_id:int
    amount:float

    model_config=ConfigDict(from_attributes=True) 


class ExpenseSplitCreate(BaseModel):
    user_id: int
    amount: float

    model_config = ConfigDict(from_attributes=True)

