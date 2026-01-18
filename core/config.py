import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    backend_url: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    use_mock: bool = os.getenv("USE_MOCK", "0") == "1"
    request_timeout_s: float = float(os.getenv("REQUEST_TIMEOUT_S", "20"))

    # "mvp" = multipart upload via backend
    # "presigned" = presign -> direct upload to storage -> complete
    upload_mode: str = os.getenv("UPLOAD_MODE", "mvp").strip().lower()


settings = Settings()

# basic validation (fail fast)
if settings.upload_mode not in ("mvp", "presigned"):
    raise ValueError("UPLOAD_MODE must be 'mvp' or 'presigned'")
