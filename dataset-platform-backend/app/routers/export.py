from __future__ import annotations

import io
import json
from datetime import datetime, timezone

import pyarrow as pa
import pyarrow.parquet as pq
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from app.core.config import get_s3_client, settings
from app.core.deps import get_current_user, get_db
from app.models.annotation import Annotation
from app.models.export import Export
from app.models.image import Image
from app.models.qc import QCRun, QCResult
from app.models.request import Request

router = APIRouter(tags=["export"])


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _require_request_access(req: Request, user) -> None:
    if user.role in ("admin", "universal"):
        return

    if user.role != "customer":
        raise HTTPException(status_code=403, detail="Forbidden")
    if req.customer_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://"):
        raise HTTPException(
            status_code=500, detail="Export storage_path is not s3://..."
        )

    rest = uri[len("s3://") :]
    bucket, _, key = rest.partition("/")
    if not bucket or not key:
        raise HTTPException(status_code=500, detail="Invalid export storage_path")
    return bucket, key


@router.post("/requests/{request_id}/export/parquet")
def export_parquet(
    request_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    req = db.get(Request, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    _require_request_access(req, user)

    total_images = (
        db.query(func.count(Image.id)).filter(Image.request_id == request_id).scalar()
        or 0
    )
    if int(total_images) == 0:
        raise HTTPException(status_code=409, detail="No images to export")

    labeled_images = (
        db.query(func.count(distinct(Annotation.image_id)))
        .join(Image, Image.id == Annotation.image_id)
        .filter(Image.request_id == request_id)
        .scalar()
        or 0
    )
    if int(labeled_images) < int(total_images):
        raise HTTPException(
            status_code=409,
            detail=f"Not all images labeled ({int(labeled_images)}/{int(total_images)})",
        )

    images = (
        db.query(Image)
        .filter(Image.request_id == request_id)
        .order_by(Image.id.asc())
        .all()
    )

    # Последняя annotation по каждому image_id
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
            ann_map[a.image_id] = a

    # QC из последнего run
    last_run = (
        db.query(QCRun)
        .filter(QCRun.request_id == request_id)
        .order_by(QCRun.id.desc())
        .first()
    )
    qc_map: dict[int, QCResult] = {}
    if last_run:
        qc_rows = (
            db.query(QCResult)
            .filter(QCResult.qc_run_id == last_run.id)  # <-- универсально
            .all()
        )
        for r in qc_rows:
            qc_map[r.image_id] = r

    out_rows = []
    for img in images:
        a = ann_map.get(img.id)
        qc = qc_map.get(img.id)

        labels_list = a.labels if a and a.labels else []

        # Если у тебя QCResult хранит JSON в поле result, то замени на:
        # dup = (qc.result or {}).get("duplicate_score")
        # ai = (qc.result or {}).get("ai_generated_score")
        # flags = (qc.result or {}).get("flags")
        dup = qc.duplicate_score if qc else None
        ai = qc.ai_generated_score if qc else None
        flags = qc.flags if qc else None

        out_rows.append(
            {
                "request_id": int(request_id),
                "image_id": int(img.id),
                "file_name": img.file_name,
                "storage_path": img.storage_path,
                "sha256": img.sha256,
                "labels": labels_list,
                "labels_json": json.dumps(labels_list, ensure_ascii=False),
                "annotation_updated_at": (a.updated_at.isoformat() if a else None),
                "duplicate_score": dup,
                "ai_generated_score": ai,
                "qc_flags": flags,
                "qc_flags_json": json.dumps(flags, ensure_ascii=False)
                if flags is not None
                else None,
            }
        )

    table = pa.Table.from_pylist(out_rows)

    buf = io.BytesIO()
    pq.write_table(table, buf)
    buf.seek(0)

    ts = _now_utc().strftime("%Y%m%d_%H%M%S_%f")
    object_key = f"requests/{request_id}/export_{ts}.parquet"

    s3 = get_s3_client()
    bucket = settings.s3_bucket_exports  # <-- ВАЖНО: snake_case

    s3.put_bytes(
        bucket=bucket,
        key=object_key,
        data=buf.read(),
        content_type="application/vnd.apache.parquet",
    )

    ex = Export(
        request_id=request_id,
        status="done",
        storage_path=f"s3://{bucket}/{object_key}",
    )
    db.add(ex)
    db.commit()
    db.refresh(ex)

    return {
        "ok": True,
        "request_id": int(request_id),
        "export_id": int(ex.id),
        "status": ex.status,
        "storage_path": ex.storage_path,
        "rows": len(out_rows),
    }


@router.get("/requests/{request_id}/export/status")
def export_status(
    request_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    req = db.get(Request, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    _require_request_access(req, user)

    ex = (
        db.query(Export)
        .filter(Export.request_id == request_id)
        .order_by(Export.id.desc())
        .first()
    )
    if not ex:
        return {"request_id": int(request_id), "status": "none"}

    return {
        "request_id": int(request_id),
        "status": ex.status,
        "export_id": int(ex.id),
        "storage_path": ex.storage_path,
        "error": getattr(ex, "error", None),
        "created_at": getattr(ex, "created_at", None),
    }


@router.get("/requests/{request_id}/export/download")
def export_download(
    request_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    req = db.get(Request, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    _require_request_access(req, user)

    ex = (
        db.query(Export)
        .filter(Export.request_id == request_id)
        .order_by(Export.id.desc())
        .first()
    )
    if not ex or not ex.storage_path:
        raise HTTPException(status_code=404, detail="Export not found")

    if ex.status != "done":
        raise HTTPException(
            status_code=409, detail=f"Export is not ready (status={ex.status})"
        )

    bucket, key = _parse_s3_uri(ex.storage_path)

    s3 = get_s3_client()
    url = s3.presign_get(bucket=bucket, key=key)
    return RedirectResponse(url, status_code=307)
