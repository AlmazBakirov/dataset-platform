from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from .s3 import S3Client, S3Config


def _detect_env_file() -> str | None:
    """
    2 режима:
    - Docker: .env.docker (db/redis/minio)
    - Local: .env (localhost)
    Приоритет:
      1) ENV_FILE (если задан и файл существует)
      2) .env.docker (если существует)
      3) .env (если существует)
      4) None (только переменные окружения)
    """
    explicit = os.getenv("ENV_FILE")
    if explicit:
        p = Path(explicit)
        if p.exists():
            return str(p)

    p_docker = Path(".env.docker")
    if p_docker.exists():
        return str(p_docker)

    p_local = Path(".env")
    if p_local.exists():
        return str(p_local)

    return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_detect_env_file(),
        env_file_encoding="utf-8",
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
    # INTERNAL: то, что доступно контейнерам (minio:9000) или локально (127.0.0.1:9000)
    s3_endpoint_url_internal: str = "http://127.0.0.1:9000"
    # PUBLIC: то, что открывает браузер/Streamlit (обычно http://localhost:9000)
    s3_endpoint_url_public: str = "http://127.0.0.1:9000"

    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_region: str = "us-east-1"

    s3_bucket_images: str = "images"
    s3_bucket_exports: str = "exports"
    s3_presign_expires_s: int = 600


settings = Settings()


@lru_cache
def get_s3_client() -> S3Client:
    """
    Важно: для presigned URL используем PUBLIC endpoint.
    Для ensure_bucket/put_bytes используем INTERNAL endpoint.
    """
    cfg = S3Config(
        endpoint_url_internal=settings.s3_endpoint_url_internal,
        endpoint_url_public=settings.s3_endpoint_url_public,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        region=settings.s3_region,
        bucket_images=settings.s3_bucket_images,
        bucket_exports=settings.s3_bucket_exports,
        presign_expires_s=settings.s3_presign_expires_s,
    )
    return S3Client(cfg)
