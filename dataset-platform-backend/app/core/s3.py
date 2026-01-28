from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlparse, urlunparse

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError


@dataclass(frozen=True)
class S3Config:
    # INTERNAL: доступно из контейнеров (minio:9000 или host.docker.internal:9000)
    endpoint_url_internal: str
    # PUBLIC: доступно браузеру/Streamlit (обычно http://localhost:9000)
    endpoint_url_public: str

    access_key: str
    secret_key: str
    region: str

    bucket_images: str
    bucket_exports: str
    presign_expires_s: int = 600


class S3Client:
    def __init__(self, cfg: S3Config) -> None:
        self.cfg = cfg
        self._client_internal = self._make_client(cfg.endpoint_url_internal)

    def _make_client(self, endpoint_url: str):
        # addressing_style=path важно для MinIO (чтобы было /bucket/key)
        return boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=self.cfg.access_key,
            aws_secret_access_key=self.cfg.secret_key,
            region_name=self.cfg.region,
            config=BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        )

    def _rewrite_to_public(self, presigned_url: str) -> str:
        """
        Presigned URL подписывается, включая host.
        Поэтому мы генерируем URL на INTERNAL endpoint, а потом аккуратно меняем
        scheme+host:port на PUBLIC endpoint (path+query оставляем как есть).
        """
        u = urlparse(presigned_url)
        pub = urlparse(self.cfg.endpoint_url_public)

        scheme = pub.scheme or u.scheme
        netloc = pub.netloc or u.netloc

        return urlunparse((scheme, netloc, u.path, u.params, u.query, u.fragment))

    # ---------- Buckets ----------
    def ensure_bucket(self, bucket: str) -> None:
        try:
            self._client_internal.head_bucket(Bucket=bucket)
            return
        except ClientError as e:
            code = str(e.response.get("Error", {}).get("Code", ""))
            # для MinIO часто прилетает 404/NoSuchBucket/NotFound
            if code not in ("404", "NoSuchBucket", "NotFound"):
                # иногда MinIO дает 400 если bucket нет — тоже попробуем создать
                pass

        try:
            self._client_internal.create_bucket(Bucket=bucket)
        except ClientError as e:
            # bucket уже может существовать (race)
            code = str(e.response.get("Error", {}).get("Code", ""))
            if code not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
                raise

    def ensure_bucket_images(self) -> None:
        self.ensure_bucket(self.cfg.bucket_images)

    def ensure_bucket_exports(self) -> None:
        self.ensure_bucket(self.cfg.bucket_exports)

    # ---------- PUT/HEAD ----------
    def put_bytes(
        self, *, bucket: str, key: str, data: bytes, content_type: str
    ) -> None:
        self.ensure_bucket(bucket)
        self._client_internal.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType=content_type or "application/octet-stream",
        )

    def head_object(self, *, bucket: str, key: str) -> dict[str, Any]:
        return self._client_internal.head_object(Bucket=bucket, Key=key)

    def head_images(self, key: str) -> dict[str, Any]:
        return self.head_object(bucket=self.cfg.bucket_images, key=key)

    # ---------- Presign ----------
    def presign_put(
        self, *, bucket: str, key: str, content_type: str, sha256: Optional[str]
    ) -> str:
        params: dict[str, Any] = {
            "Bucket": bucket,
            "Key": key,
            "ContentType": content_type or "application/octet-stream",
        }
        if sha256:
            # мы проверяем это в /uploads/confirm через head_object().Metadata
            params["Metadata"] = {"sha256": sha256}

        url = self._client_internal.generate_presigned_url(
            ClientMethod="put_object",
            Params=params,
            ExpiresIn=int(self.cfg.presign_expires_s),
        )
        return self._rewrite_to_public(url)

    def presign_get(self, *, bucket: str, key: str) -> str:
        url = self._client_internal.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=int(self.cfg.presign_expires_s),
        )
        return self._rewrite_to_public(url)

    def presign_put_images(
        self, object_key: str, content_type: str, sha256: Optional[str]
    ) -> str:
        # bucket для images берем из cfg
        return self.presign_put(
            bucket=self.cfg.bucket_images,
            key=object_key,
            content_type=content_type,
            sha256=sha256,
        )
