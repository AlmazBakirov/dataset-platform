from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json

from celery import shared_task
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.request import Request
from app.models.image import Image

# QC модели (ожидается, что у вас есть QCRun/QCResult; если имена другие — замените импорты)
from app.models.qc import QCRun, QCResult

# Tasks модели (у вас есть Task/TaskImage)
from app.models.task import Task, TaskImage
from app.models.user import User

# Export модель (создадим ниже как app.models.export.Export)
from app.models.export import Export

import pyarrow as pa
import pyarrow.parquet as pq


def _now():
    return datetime.now(timezone.utc)


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _calc_duplicates_by_sha(images: list[Image]) -> dict[int, int | None]:
    """
    Возвращает dict: image_id -> duplicate_of_image_id (или None).
    Exact-duplicate по sha256.
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

    # привяжем все images
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

        # статус running
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

        # очистим результаты этого run (если job ретраится)
        db.query(QCResult).filter(QCResult.qc_run_id == run.id).delete()
        db.commit()

        dup_of = _calc_duplicates_by_sha(images)

        # создаём qc results (MVP — exact dup + заглушка ai_score)
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

        # создаём task, если ещё нет
        _ensure_task_for_request(db, run.request_id)

        run.status = "done"
        run.finished_at = _now()
        db.commit()

        return {"ok": True, "qc_run_id": run.id, "status": run.status}

    except Exception as e:
        db.rollback()
        # если run существует — пометим failed
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

        # Собираем данные для parquet (MVP)
        images = db.query(Image).filter(Image.request_id == exp.request_id).all()
        if not images:
            exp.status = "failed"
            exp.error = "No images"
            exp.finished_at = _now()
            db.commit()
            return {"ok": False, "error": exp.error}

        # labels берём из annotations (у вас уже есть таблица annotations)
        # Если у вас другие имена/модель — поправьте импорт/запрос.
        from app.models.annotation import (
            Annotation,
        )  # локальный импорт чтобы избежать циклов

        rows = []
        for img in images:
            ann = (
                db.query(Annotation)
                .filter(Annotation.image_id == img.id)
                .order_by(Annotation.updated_at.desc())
                .first()
            )
            labels = ann.labels if ann else None

            rows.append(
                {
                    "request_id": int(exp.request_id),
                    "image_id": int(img.id),
                    "file_name": img.file_name,
                    "storage_path": img.storage_path,
                    "sha256": img.sha256,
                    "labels_json": json.dumps(labels) if labels is not None else None,
                }
            )

        table = pa.Table.from_pylist(rows)

        out_dir = Path("storage") / "exports"
        _ensure_dir(out_dir)

        out_path = out_dir / f"request_{exp.request_id}_export_{exp.id}.parquet"
        pq.write_table(table, out_path)

        exp.status = "done"
        exp.storage_path = str(out_path)
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
