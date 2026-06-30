from pydantic import BaseModel


class AddMember(BaseModel):
    email: str