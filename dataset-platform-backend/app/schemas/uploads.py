from __future__ import annotations
from pydantic import BaseModel
from datetime import datetime


class ImageOut(BaseModel):
    id: int
    request_id: int
    file_name: str
    content_type: str
    storage_path: str
    sha256: str
    created_at: datetime

    class Config:
        from_attributes = True


class PresignUploadIn(BaseModel):
    request_id: int
    file_name: str
    content_type: str = "application/octet-stream"
    sha256: str | None = None  # UI может посчитать и отправить (рекомендуется)


class PresignUploadOut(BaseModel):
    upload_url: str
    object_key: str
    bucket: str
    expires_in: int


class ConfirmUploadIn(BaseModel):
    request_id: int
    file_name: str
    content_type: str
    object_key: str
    sha256: str | None = None


class ConfirmUploadOut(BaseModel):
    image_id: int
    request_id: int
    file_name: str
    storage_path: str
    sha256: str | None
