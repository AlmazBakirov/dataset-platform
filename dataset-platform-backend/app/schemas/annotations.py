from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SaveLabelsIn(BaseModel):
    image_id: int
    labels: Any


class SaveLabelsOut(BaseModel):
    status: str
    task_id: int
    image_id: int
    labels: Any


class AnnotationOut(BaseModel):
    id: int
    task_id: int
    image_id: int
    labeler_id: int
    labels: Any
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
