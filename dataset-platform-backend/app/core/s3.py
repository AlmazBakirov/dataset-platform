from __future__ import annotations

import boto3
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse


@dataclass(frozen=True)
class S3Config:
    # Внутренний endpoint для SDK (в docker-сети): например http://minio:9000
    endpoint_url: str

    # Публичный endpoint для браузера/Streamlit (на хосте): например http://localhost:9000
    # Если None — URL не переписываем
    public_endpoint_url: str | None = None

    access_key: str = "minioadmin"
    secret_key: str = "minioadmin"
    region: str = "us-east-1"

    bucket_images: str = "images"
    bucket_exports: str = "exports"
    presign_expires_s: int = 600


class S3Client:
    def __init__(self, cfg: S3Config):
        self.cfg = cfg
        self._client = boto3.client(
            "s3",
            endpoint_url=cfg.endpoint_url,
            aws_access_key_id=cfg.access_key,
            aws_secret_access_key=cfg.secret_key,
            region_name=cfg.region,
        )
        self._public = (
            urlparse(cfg.public_endpoint_url) if cfg.public_endpoint_url else None
        )

    def _rewrite_to_public(self, url: str) -> str:
        """
        Важно: подпись в presigned URL зависит от path+query,
        но НЕ зависит от host. Поэтому можем безопасно заменить host/scheme.
        """
        if not self._public:
            return url
        u = urlparse(url)
        return urlunparse(
            (
                self._public.scheme,
                self._public.netloc,
                u.path,
                u.params,
                u.query,
                u.fragment,
            )
        )

    def presign_put(self, bucket: str, key: str, content_type: str) -> str:
        url = self._client.generate_presigned_url(
            ClientMethod="put_object",
            Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=int(self.cfg.presign_expires_s),
        )
        return self._rewrite_to_public(url)

    def presign_get(self, bucket: str, key: str) -> str:
        url = self._client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=int(self.cfg.presign_expires_s),
        )
        return self._rewrite_to_public(url)

    def put_bytes(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        self._client.put_object(
            Bucket=bucket, Key=key, Body=data, ContentType=content_type
        )

    def object_exists(self, bucket: str, key: str) -> bool:
        try:
            self._client.head_object(Bucket=bucket, Key=key)
            return True
        except Exception:
            return False

    def ensure_bucket(self, bucket: str) -> None:
        try:
            self._client.head_bucket(Bucket=bucket)
        except Exception:
            self._client.create_bucket(Bucket=bucket)
