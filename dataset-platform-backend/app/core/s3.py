from __future__ import annotations

from dataclasses import dataclass

import boto3


@dataclass(frozen=True)
class S3Config:
    endpoint_url: str
    access_key: str
    secret_key: str
    region: str
    bucket_images: str
    bucket_exports: str
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

    def presign_put(self, bucket: str, key: str, content_type: str) -> str:
        return self._client.generate_presigned_url(
            ClientMethod="put_object",
            Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=int(self.cfg.presign_expires_s),
        )

    def presign_get(self, bucket: str, key: str) -> str:
        return self._client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=int(self.cfg.presign_expires_s),
        )

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
