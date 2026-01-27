from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.core.config import get_s3_client
from app.core.deps import get_db, get_current_user
from app.models.image import Image
from app.models.request import Request

router = APIRouter(tags=["images"])


def _require_image_access(img: Image, db: Session, user) -> None:
    # labeler/admin/universal могут получать через задачу — у вас уже RBAC по tasks.
    # Для простоты: разрешим всем авторизованным, кроме customer проверим ownership по request.
    if user.role in ("admin", "universal", "labeler"):
        return

    if user.role != "customer":
        raise HTTPException(status_code=403, detail="Forbidden")

    req = db.get(Request, img.request_id)
    if not req or req.customer_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/images/{image_id}/content")
def get_image_content(
    image_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    img = db.get(Image, image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    _require_image_access(img, db, user)

    # Если storage_path локальный — отдаём FileResponse (старый режим)
    if img.storage_path and not img.storage_path.startswith("s3://"):
        return FileResponse(
            img.storage_path, media_type=img.content_type or "application/octet-stream"
        )

    # Если storage_path s3://bucket/key — делаем presigned GET и редирект
    if not img.storage_path or not img.storage_path.startswith("s3://"):
        raise HTTPException(status_code=500, detail="Invalid storage_path")

    # parse: s3://bucket/key
    _, _, rest = img.storage_path.partition("s3://")
    bucket, _, key = rest.partition("/")
    if not bucket or not key:
        raise HTTPException(status_code=500, detail="Invalid s3 storage_path")

    s3 = get_s3_client()
    url = s3.presign_get(bucket=bucket, key=key)

    # 307: сохраняет метод (GET) и обычно нормально обрабатывается клиентами
    return RedirectResponse(url, status_code=307)
