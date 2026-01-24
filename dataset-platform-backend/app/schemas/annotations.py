from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel


class SaveLabelsIn(BaseModel):
    image_id: int
    labels: List[str]  # строгий стандарт: всегда список строк


class SaveLabelsOut(BaseModel):
    status: str
    task_id: int
    image_id: int
    labeler_id: int
    labels: List[str]


class AnnotationOut(BaseModel):
    id: int
    task_id: int
    image_id: int
    labeler_id: int
    labels: List[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
