from __future__ import annotations
import hashlib
from typing import List
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings, get_s3_client
from app.core.deps import get_db, get_current_user
from app.models.image import Image
from app.models.request import Request
from app.schemas.uploads import ImageOut
from app.schemas.uploads import (
    ConfirmUploadIn,
    ConfirmUploadOut,
    PresignUploadIn,
    PresignUploadOut,
)

router = APIRouter(tags=["uploads"])


def _require_request_access(req: Request, user) -> None:
    if user.role in ("admin", "universal"):
        return
    if user.role != "customer":
        raise HTTPException(status_code=403, detail="Forbidden")
    if req.customer_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/uploads/presign", response_model=PresignUploadOut)
def presign_upload(
    payload: PresignUploadIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if not payload.sha256:
        raise HTTPException(
            status_code=400, detail="sha256 is required for presigned upload"
        )

    req: Request | None = db.get(Request, payload.request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    _require_request_access(req, user)

    # object key: images/requests/{request_id}/{timestamp}_{filename}
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    safe_name = payload.file_name.replace("\\", "_").replace("/", "_")
    object_key = f"requests/{payload.request_id}/{ts}_{safe_name}"

    s3 = get_s3_client()
    upload_url = s3.presign_put(
        bucket=settings.s3_bucket_images,
        key=object_key,
        content_type=payload.content_type or "application/octet-stream",
        sha256=payload.sha256,
    )

    return PresignUploadOut(
        upload_url=upload_url,
        object_key=object_key,
        bucket=settings.s3_bucket_images,
        expires_in=int(settings.s3_presign_expires_s),
    )


@router.post("/uploads/confirm", response_model=ConfirmUploadOut)
def confirm_upload(
    payload: ConfirmUploadIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    req = db.get(Request, payload.request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    _require_request_access(req, user)
    if not payload.sha256:
        raise HTTPException(
            status_code=400, detail="sha256 is required for confirm_upload"
        )

    s3 = get_s3_client()
    if not s3.object_exists(settings.s3_bucket_images, payload.object_key):
        raise HTTPException(status_code=400, detail="Object not found in S3 bucket")

    # storage_path теперь хранит s3://bucket/key (или просто key — но лучше явно)
    storage_path = f"s3://{settings.s3_bucket_images}/{payload.object_key}"

    img = Image(
        request_id=payload.request_id,
        file_name=payload.file_name,
        content_type=payload.content_type,
        storage_path=storage_path,
        sha256=payload.sha256,
    )
    db.add(img)
    db.commit()
    db.refresh(img)

    return ConfirmUploadOut(
        image_id=img.id,
        request_id=img.request_id,
        file_name=img.file_name,
        storage_path=img.storage_path,
        sha256=img.sha256,
    )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_filename(name: str) -> str:
    # минимальная защита от странных путей/символов
    name = (name or "file.bin").replace("\\", "_").replace("/", "_").strip()
    return name if name else "file.bin"


@router.post("/requests/{request_id}/uploads", response_model=List[ImageOut])
def upload_files_mvp(
    request_id: int,
    files: List[UploadFile] = File(...),  # UI отправляет именно files=...
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    req = db.get(Request, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    if user.role == "customer" and req.customer_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    storage_root = Path(settings.storage_dir) / "requests" / str(request_id)
    storage_root.mkdir(parents=True, exist_ok=True)

    created: List[Image] = []

    for f in files:
        data = f.file.read()
        if not data:
            continue

        digest = _sha256(data)
        safe_name = _safe_filename(f.filename)
        out_path = storage_root / safe_name

        # если файл с таким именем уже есть — добавим префикс sha256
        if out_path.exists():
            out_path = storage_root / f"{digest}_{safe_name}"

        out_path.write_bytes(data)

        img = Image(
            request_id=request_id,
            file_name=safe_name,
            content_type=f.content_type or "application/octet-stream",
            storage_path=str(out_path),
            sha256=digest,
        )
        db.add(img)
        created.append(img)

    db.commit()
    for img in created:
        db.refresh(img)

    return created


@router.get("/requests/{request_id}/uploads", response_model=List[ImageOut])
def list_uploads(
    request_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    req = db.get(Request, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    if user.role == "customer" and req.customer_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    return (
        db.query(Image)
        .filter(Image.request_id == request_id)
        .order_by(Image.id.desc())
        .all()
    )
