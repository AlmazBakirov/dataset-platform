import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    backend_url: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    use_mock: bool = os.getenv("USE_MOCK", "0") == "1"
    request_timeout_s: float = float(os.getenv("REQUEST_TIMEOUT_S", "20"))

settings = Settings()
