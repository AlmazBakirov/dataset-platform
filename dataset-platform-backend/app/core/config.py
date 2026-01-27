import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.s3 import S3Client, S3Config


def _detect_env_file() -> str | None:
    """
    1) Если задан ENV_FILE и такой файл существует — читаем его.
    2) Иначе, если рядом есть .env — читаем его.
    3) Иначе — НЕ читаем dotenv, берём только переменные окружения (Docker env).
    """
    env_file = os.getenv("ENV_FILE")
    if env_file:
        p = Path(env_file)
        if p.exists():
            return str(p)

    p = Path(".env")
    return str(p) if p.exists() else None


class Settings(BaseSettings):
    # Важно:
    # - extra="ignore": чтобы приложение не падало, если в env есть "лишние" ключи
    # - env_file=_detect_env_file(): чтобы в Docker не схватить случайный .env из образа
    # - case_sensitive=False: чтобы нормально читались DATABASE_URL / database_url и т.д.
    model_config = SettingsConfigDict(
        env_file=_detect_env_file(),
        extra="ignore",
        case_sensitive=False,
    )

    # DB / Auth
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/dataset_platform"
    )
    storage_dir: str = "./storage"
    jwt_secret: str = "change_me"
    jwt_alg: str = "HS256"
    access_token_expire_minutes: int = 120

    # Celery
    celery_broker_url: str = "redis://127.0.0.1:6379/0"
    celery_result_backend: str = "redis://127.0.0.1:6379/1"

    # ---------- S3 / MinIO ----------
    s3_endpoint_url: str = "http://127.0.0.1:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_region: str = "us-east-1"
    s3_bucket_images: str = "images"
    s3_bucket_exports: str = "exports"
    s3_presign_expires_s: int = 600


settings = Settings()


def get_s3_client() -> S3Client:
    """
    Helper, чтобы в роутерах вы делали:
      from app.core.config import get_s3_client, settings
      s3 = get_s3_client()
    """
    cfg = S3Config(
        endpoint_url=settings.s3_endpoint_url,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        region=settings.s3_region,
        bucket_images=settings.s3_bucket_images,
        bucket_exports=settings.s3_bucket_exports,
        presign_expires_s=settings.s3_presign_expires_s,
    )
    return S3Client(cfg)
