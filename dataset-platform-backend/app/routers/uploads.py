import hashlib
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db, get_current_user
from app.models.request import Request
from app.models.image import Image
from app.schemas.uploads import ImageOut

router = APIRouter(tags=["uploads"])


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
