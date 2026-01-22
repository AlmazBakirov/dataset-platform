from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.image import Image

router = APIRouter(tags=["images"])


@router.get("/images/{image_id}/content")
def get_image_content(
    image_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    img = db.get(Image, image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    # storage_path у тебя относительный: "storage\\requests\\5\\file.jpg"
    path = Path(img.storage_path)
    if not path.is_absolute():
        # корень проекта = текущая рабочая директория uvicorn
        path = (Path.cwd() / path).resolve()

    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    return FileResponse(
        str(path),
        media_type=img.content_type or "application/octet-stream",
        filename=img.file_name,
    )
