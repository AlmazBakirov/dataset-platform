from datetime import datetime
from pydantic import BaseModel


class QCRunOut(BaseModel):
    id: int
    request_id: int
    status: str
    params: dict
    error: str | None
    started_at: datetime
    finished_at: datetime | None

    class Config:
        from_attributes = True


class QCResultOut(BaseModel):
    id: int
    qc_run_id: int
    request_id: int
    image_id: int

    duplicate_score: float
    duplicate_of_image_id: int | None
    ai_generated_score: float
    flags: dict
    created_at: datetime

    class Config:
        from_attributes = True
