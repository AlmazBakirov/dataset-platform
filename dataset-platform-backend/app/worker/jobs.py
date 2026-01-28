from __future__ import annotations

from datetime import datetime, timezone
import json
import io

from celery import shared_task
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.core.config import get_s3_client, settings

from app.models.request import Request
from app.models.image import Image
from app.models.qc import QCRun, QCResult
from app.models.task import Task, TaskImage
from app.models.user import User
from app.models.export import Export
from app.models.annotation import Annotation

import pyarrow as pa
import pyarrow.parquet as pq


def _now():
    return datetime.now(timezone.utc)


def _calc_duplicates_by_sha(images: list[Image]) -> dict[int, int | None]:
    """
    dict: image_id -> duplicate_of_image_id (или None)
    Exact duplicate по sha256.
    """
    seen: dict[str, int] = {}
    dup_of: dict[int, int | None] = {}

    for img in images:
        sha = (img.sha256 or "").strip()
        if sha and sha in seen:
            dup_of[img.id] = seen[sha]
        else:
            if sha:
                seen[sha] = img.id
            dup_of[img.id] = None
    return dup_of


def _assign_labeler(db: Session) -> int:
    labeler = (
        db.query(User)
        .filter(User.role == "labeler", User.is_active == True)  # noqa: E712
        .order_by(User.id.asc())
        .first()
    )
    if not labeler:
        raise RuntimeError("No active labeler found")
    return int(labeler.id)


def _ensure_task_for_request(db: Session, request_id: int) -> int:
    """
    Создаёт задачу разметки на всю заявку (MVP).
    Если задача уже есть — возвращает её id.
    """
    existing = (
        db.query(Task)
        .filter(Task.request_id == request_id)
        .order_by(Task.id.desc())
        .first()
    )
    if existing:
        return int(existing.id)

    assigned_to = _assign_labeler(db)
    task = Task(request_id=request_id, assigned_to=assigned_to, status="open")
    db.add(task)
    db.flush()  # получить task.id

    images = db.query(Image).filter(Image.request_id == request_id).all()
    for img in images:
        db.add(TaskImage(task_id=task.id, image_id=img.id))

    return int(task.id)


@shared_task(name="qc.run_qc")
def qc_run_job(qc_run_id: int) -> dict:
    db = SessionLocal()
    try:
        run = db.get(QCRun, qc_run_id)
        if not run:
            raise RuntimeError("QCRun not found")

        req = db.get(Request, run.request_id)
        if not req:
            raise RuntimeError("Request not found")

        run.status = "running"
        run.started_at = _now()
        run.error = None
        db.commit()

        images = db.query(Image).filter(Image.request_id == run.request_id).all()
        if not images:
            run.status = "failed"
            run.error = "No uploads for this request"
            run.finished_at = _now()
            db.commit()
            return {"ok": False, "error": run.error}

        # идемпотентность: если ретрай — пересоздадим результаты
        db.query(QCResult).filter(QCResult.qc_run_id == run.id).delete()
        db.commit()

        dup_of = _calc_duplicates_by_sha(images)

        for img in images:
            d_of = dup_of.get(img.id)
            duplicate_score = 1.0 if d_of is not None else 0.0
            flags = {}
            if d_of is not None:
                flags["DUPLICATE"] = True

            r = QCResult(
                qc_run_id=run.id,
                request_id=run.request_id,
                image_id=img.id,
                duplicate_score=duplicate_score,
                duplicate_of_image_id=d_of,
                ai_generated_score=0.0,
                flags=flags,
            )
            db.add(r)

        _ensure_task_for_request(db, run.request_id)

        run.status = "done"
        run.finished_at = _now()
        db.commit()

        return {"ok": True, "qc_run_id": run.id, "status": run.status}

    except Exception as e:
        db.rollback()
        try:
            run = db.get(QCRun, qc_run_id)
            if run:
                run.status = "failed"
                run.error = str(e)
                run.finished_at = _now()
                db.commit()
        except Exception:
            pass
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


@shared_task(name="export.build_parquet")
def export_job(export_id: int) -> dict:
    """
    Асинхронная сборка parquet в S3/MinIO.
    Пишет storage_path в формате: s3://<bucket>/<key>
    """
    db = SessionLocal()
    try:
        exp = db.get(Export, export_id)
        if not exp:
            raise RuntimeError("Export not found")

        req = db.get(Request, exp.request_id)
        if not req:
            raise RuntimeError("Request not found")

        exp.status = "running"
        exp.started_at = _now()
        exp.error = None
        db.commit()

        images = (
            db.query(Image)
            .filter(Image.request_id == exp.request_id)
            .order_by(Image.id.asc())
            .all()
        )
        if not images:
            exp.status = "failed"
            exp.error = "No images"
            exp.finished_at = _now()
            db.commit()
            return {"ok": False, "error": exp.error}

        # проверка: все изображения размечены (хотя бы 1 annotation на image_id)
        image_ids = [img.id for img in images]
        labeled_ids = {
            r[0]
            for r in db.query(Annotation.image_id)
            .filter(Annotation.image_id.in_(image_ids))
            .distinct()
            .all()
        }
        if len(labeled_ids) != len(image_ids):
            missing = sorted(set(image_ids) - labeled_ids)
            exp.status = "failed"
            exp.error = f"Not all images labeled. Missing image_ids: {missing[:20]}" + (
                " ..." if len(missing) > 20 else ""
            )
            exp.finished_at = _now()
            db.commit()
            return {"ok": False, "error": exp.error}

        # qc_map по последнему QC run
        last_run = (
            db.query(QCRun)
            .filter(QCRun.request_id == exp.request_id)
            .order_by(QCRun.id.desc())
            .first()
        )
        qc_map: dict[int, QCResult] = {}
        if last_run:
            qc_rows = db.query(QCResult).filter(QCResult.qc_run_id == last_run.id).all()
            for r in qc_rows:
                qc_map[int(r.image_id)] = r

        # ann_map: берём самую свежую annotation на image_id
        ann_rows = (
            db.query(Annotation)
            .filter(Annotation.image_id.in_(image_ids))
            .order_by(Annotation.image_id.asc(), Annotation.updated_at.desc())
            .all()
        )
        ann_map: dict[int, Annotation] = {}
        for a in ann_rows:
            iid = int(a.image_id)
            if iid not in ann_map:
                ann_map[iid] = a

        out_rows = []
        for img in images:
            ann = ann_map.get(int(img.id))
            labels = ann.labels if ann else None
            ann_updated = ann.updated_at.isoformat() if ann and ann.updated_at else None

            qc = qc_map.get(int(img.id))
            qc_flags = qc.flags if qc else None

            out_rows.append(
                {
                    "request_id": int(exp.request_id),
                    "image_id": int(img.id),
                    "file_name": img.file_name,
                    "storage_path": img.storage_path,
                    "sha256": img.sha256,
                    "labels": labels,
                    "labels_json": json.dumps(labels) if labels is not None else None,
                    "annotation_updated_at": ann_updated,
                    "duplicate_score": float(qc.duplicate_score) if qc else None,
                    "ai_generated_score": float(qc.ai_generated_score) if qc else None,
                    "qc_flags": qc_flags,
                    "qc_flags_json": json.dumps(qc_flags)
                    if qc_flags is not None
                    else None,
                }
            )

        table = pa.Table.from_pylist(out_rows)

        buf = io.BytesIO()
        pq.write_table(table, buf)
        data = buf.getvalue()

        # кладём parquet в exports bucket
        s3 = get_s3_client()
        bucket = settings.s3_bucket_exports
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        key = f"requests/{exp.request_id}/exports/export_{ts}_{exp.id}.parquet"

        s3.put_bytes(
            bucket=bucket, key=key, data=data, content_type="application/octet-stream"
        )

        exp.status = "done"
        exp.storage_path = f"s3://{bucket}/{key}"
        exp.finished_at = _now()
        db.commit()

        return {
            "ok": True,
            "export_id": exp.id,
            "status": exp.status,
            "storage_path": exp.storage_path,
        }

    except Exception as e:
        db.rollback()
        try:
            exp = db.get(Export, export_id)
            if exp:
                exp.status = "failed"
                exp.error = str(e)
                exp.finished_at = _now()
                db.commit()
        except Exception:
            pass
        return {"ok": False, "error": str(e)}
    finally:
        db.close()
