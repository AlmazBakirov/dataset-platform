from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.deps import get_db, get_current_user
from app.models.request import Request
from app.models.image import Image
from app.models.qc import QCRun, QCResult
from app.worker.celery_app import celery_app

router = APIRouter(tags=["qc"])


def _now():
    return datetime.now(timezone.utc)


@router.post("/requests/{request_id}/qc/run")
def qc_run(
    request_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        req = db.get(Request, request_id)
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")

        if user.role == "customer" and req.customer_id != user.id:
            raise HTTPException(status_code=403, detail="Forbidden")

        # защита от дублей: если уже есть queued/running — не создаём новый
        active = (
            db.query(QCRun)
            .filter(
                QCRun.request_id == request_id, QCRun.status.in_(["queued", "running"])
            )
            .order_by(QCRun.id.desc())
            .first()
        )
        if active:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "QC already running",
                    "qc_run_id": active.id,
                    "status": active.status,
                    "celery_task_id": active.celery_task_id,
                },
            )

        # sanity: есть ли uploads
        count_images = (
            db.query(func.count(Image.id))
            .filter(Image.request_id == request_id)
            .scalar()
            or 0
        )
        if int(count_images) == 0:
            raise HTTPException(status_code=400, detail="No uploads for this request")

        run = QCRun(
            request_id=request_id,
            status="queued",
            params={},
            created_at=_now(),
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        # ставим job (может упасть если брокер недоступен/неверный URL)
        try:
            async_res = celery_app.send_task("qc.run_qc", args=[run.id])
        except Exception as e:
            run.status = "failed"
            run.error = f"Failed to enqueue Celery task: {e}"
            run.finished_at = _now()
            db.commit()
            raise HTTPException(
                status_code=503,
                detail={
                    "message": "Failed to enqueue QC job (Celery/Redis problem)",
                    "error": str(e),
                },
            )

        run.celery_task_id = async_res.id
        db.commit()

        return {
            "qc_run_id": run.id,
            "request_id": request_id,
            "status": run.status,
            "celery_task_id": run.celery_task_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        # максимально полезно для отладки (чтобы не было немого 500)
        raise HTTPException(
            status_code=500, detail={"message": "QC run failed", "error": str(e)}
        )


@router.get("/requests/{request_id}/qc/status")
def qc_status(
    request_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    req = db.get(Request, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    if user.role == "customer" and req.customer_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    run = (
        db.query(QCRun)
        .filter(QCRun.request_id == request_id)
        .order_by(QCRun.id.desc())
        .first()
    )
    if not run:
        return {"request_id": request_id, "status": "no_runs"}

    total_images = (
        db.query(func.count(Image.id)).filter(Image.request_id == request_id).scalar()
        or 0
    )
    processed = (
        db.query(func.count(QCResult.id)).filter(QCResult.qc_run_id == run.id).scalar()
        or 0
    )

    return {
        "qc_run_id": run.id,
        "request_id": request_id,
        "status": run.status,
        "error": run.error,
        "total_images": int(total_images),
        "processed_images": int(processed),
        "celery_task_id": run.celery_task_id,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
    }


@router.get("/requests/{request_id}/qc/results")
def qc_results(
    request_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    req = db.get(Request, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    if user.role == "customer" and req.customer_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    run = (
        db.query(QCRun)
        .filter(QCRun.request_id == request_id)
        .order_by(QCRun.id.desc())
        .first()
    )
    if not run or run.status != "done":
        return []

    return (
        db.query(QCResult)
        .filter(QCResult.request_id == request_id, QCResult.qc_run_id == run.id)
        .order_by(QCResult.id.asc())
        .all()
    )
