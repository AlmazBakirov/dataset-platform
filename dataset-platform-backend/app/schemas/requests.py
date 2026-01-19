from pydantic import BaseModel, Field


class CreateRequestIn(BaseModel):
    title: str = Field(min_length=1)
    description: str = ""
    classes: list[str] = []


class RequestOut(BaseModel):
    id: str
    title: str
    description: str
    classes: list[str]
    status: str
