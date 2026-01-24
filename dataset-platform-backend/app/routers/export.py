from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime

import pyarrow as pa
import pyarrow.parquet as pq
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct

from app.core.deps import get_db, get_current_user
from app.models.request import Request
from app.models.image import Image
from app.models.annotation import Annotation
from app.models.qc import QCRun, QCResult
from app.models.user import User

router = APIRouter(tags=["export"])


def _export_path(request_id: int) -> Path:
    out_dir = Path("storage") / "exports" / "requests" / str(request_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / "dataset.parquet"


@router.post("/requests/{request_id}/export/parquet")
def export_parquet(
    request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Доступ: customer видит только свои requests; admin/universal видит всё
    req = db.get(Request, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    if user.role == "customer" and req.customer_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    if user.role not in ("customer", "admin", "universal"):
        raise HTTPException(status_code=403, detail="Forbidden")

    # 1) Считаем total images
    total_images = (
        db.query(func.count(Image.id)).filter(Image.request_id == request_id).scalar()
        or 0
    )
    if total_images == 0:
        raise HTTPException(status_code=409, detail="No images to export")

    # 2) Считаем labeled images (любая разметка по image_id в этом request)
    labeled_images = (
        db.query(func.count(distinct(Annotation.image_id)))
        .join(Image, Image.id == Annotation.image_id)
        .filter(Image.request_id == request_id)
        .scalar()
        or 0
    )

    if labeled_images < total_images:
        raise HTTPException(
            status_code=409,
            detail=f"Not all images labeled ({labeled_images}/{total_images})",
        )

    # 3) Забираем все images
    images = (
        db.query(Image)
        .filter(Image.request_id == request_id)
        .order_by(Image.id.asc())
        .all()
    )

    # 4) Забираем annotations и берём "последнюю" для каждого image_id (по updated_at)
    anns = (
        db.query(Annotation)
        .join(Image, Image.id == Annotation.image_id)
        .filter(Image.request_id == request_id)
        .order_by(Annotation.image_id.asc(), Annotation.updated_at.desc())
        .all()
    )

    ann_map: dict[int, Annotation] = {}
    for a in anns:
        if a.image_id not in ann_map:
            ann_map[a.image_id] = a  # первая будет самой новой из-за сортировки

    # 5) Забираем QC results последнего QC run (если есть)
    last_run = (
        db.query(QCRun)
        .filter(QCRun.request_id == request_id)
        .order_by(QCRun.id.desc())
        .first()
    )
    qc_map: dict[int, QCResult] = {}
    if last_run:
        rows = (
            db.query(QCResult)
            .filter(
                QCResult.request_id == request_id, QCResult.qc_run_id == last_run.id
            )
            .all()
        )
        for r in rows:
            qc_map[r.image_id] = r

    # 6) Собираем строки под parquet
    out_rows = []
    for img in images:
        a = ann_map.get(img.id)
        qc = qc_map.get(img.id)

        out_rows.append(
            {
                "request_id": request_id,
                "image_id": img.id,
                "file_name": img.file_name,
                "storage_path": img.storage_path,
                "sha256": img.sha256,
                "labels_json": json.dumps(a.labels if a else None, ensure_ascii=False),
                "annotation_updated_at": (a.updated_at.isoformat() if a else None),
                "duplicate_score": (qc.duplicate_score if qc else None),
                "ai_generated_score": (qc.ai_generated_score if qc else None),
                "qc_flags_json": json.dumps(
                    qc.flags if qc else None, ensure_ascii=False
                ),
            }
        )

    # 7) Пишем parquet
    table = pa.Table.from_pylist(out_rows)
    out_path = _export_path(request_id)
    pq.write_table(table, out_path)

    return {
        "ok": True,
        "status": "done",
        "request_id": request_id,
        "file": str(out_path),
        "download_url": f"/requests/{request_id}/export/download",
        "exported_at": datetime.utcnow().isoformat(),
        "rows": len(out_rows),
    }


@router.get("/requests/{request_id}/export/status")
def export_status(
    request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    req = db.get(Request, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    if user.role == "customer" and req.customer_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    out_path = _export_path(request_id)
    if not out_path.exists():
        return {"ok": True, "status": "not_found", "request_id": request_id}

    stat = out_path.stat()
    return {
        "ok": True,
        "status": "done",
        "request_id": request_id,
        "download_url": f"/requests/{request_id}/export/download",
        "size_bytes": stat.st_size,
        "mtime": datetime.utcfromtimestamp(stat.st_mtime).isoformat(),
    }


@router.get("/requests/{request_id}/export/download")
def export_download(
    request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    req = db.get(Request, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    if user.role == "customer" and req.customer_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    out_path = _export_path(request_id)
    if not out_path.exists():
        raise HTTPException(
            status_code=404, detail="Export not found. Run export first."
        )

    return FileResponse(
        str(out_path),
        media_type="application/octet-stream",
        filename=f"request_{request_id}.parquet",
    )
