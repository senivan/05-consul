from pydantic import BaseModel, Field


class MessageIn(BaseModel):
    message: str = Field(min_length=1)


class MessageOut(BaseModel):
    id: str
    message: str

