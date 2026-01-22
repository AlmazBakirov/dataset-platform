from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class TaskListOut(BaseModel):
    id: int
    request_id: int
    assigned_to: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class TaskImageOut(BaseModel):
    image_id: int
    url: Optional[str] = None


class TaskDetailOut(BaseModel):
    id: int
    title: str
    request_id: int
    status: str
    classes: List[str]
    images: List[TaskImageOut]
