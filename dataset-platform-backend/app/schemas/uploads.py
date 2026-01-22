from datetime import datetime
from pydantic import BaseModel


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
