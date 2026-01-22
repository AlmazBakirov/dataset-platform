from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.request import Request
from app.models.image import Image
from app.models.qc import QCRun, QCResult
from app.models.user import User
from app.models.task import Task, TaskImage
from app.schemas.qc import QCRunOut, QCResultOut

router = APIRouter(tags=["qc"])


def ensure_task_for_request(db: Session, request_id: int) -> Task:
    # если задача уже есть — вернем её
    task = (
        db.query(Task)
        .filter(Task.request_id == request_id)
        .order_by(Task.id.desc())
        .first()
    )
    if task:
        return task

    # найдём любого активного labeler-а
    labeler = (
        db.query(User)
        .filter(User.role == "labeler", User.is_active == True)  # noqa: E712
        .order_by(User.id.asc())
        .first()
    )
    if not labeler:
        raise HTTPException(
            status_code=500,
            detail="No active labeler found to assign the task. Create labeler1 or make tasks.assigned_to nullable.",
        )

    task = Task(request_id=request_id, assigned_to=labeler.id, status="open")
    db.add(task)
    db.flush()  # получаем task.id без commit

    images = db.query(Image).filter(Image.request_id == request_id).all()
    for img in images:
        db.add(TaskImage(task_id=task.id, image_id=img.id))

    return task


@router.post("/requests/{request_id}/qc/run", response_model=QCRunOut)
def run_qc(
    request_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    req = db.get(Request, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    if user.role == "customer" and req.customer_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Берём все изображения заявки
    images = db.query(Image).filter(Image.request_id == request_id).all()
    if not images:
        raise HTTPException(status_code=400, detail="No uploads for this request")

    # Создаём QC run
    qc_run = QCRun(
        request_id=request_id,
        status="running",
        params={"duplicate_threshold": 0.85, "ai_threshold": 0.8},
        started_at=datetime.now(timezone.utc),
    )
    db.add(qc_run)
    db.commit()
    db.refresh(qc_run)

    # MVP "фейковый" QC:
    # - duplicate_score = 0.0
    # - ai_generated_score = 0.1
    # - flags пустые
    results: list[QCResult] = []
    for img in images:
        r = QCResult(
            qc_run_id=qc_run.id,
            request_id=request_id,
            image_id=img.id,
            duplicate_score=0.0,
            duplicate_of_image_id=None,
            ai_generated_score=0.1,
            flags={},
        )
        db.add(r)
        results.append(r)

    qc_run.status = "done"
    qc_run.finished_at = datetime.now(timezone.utc)
    db.add(qc_run)

    ensure_task_for_request(db, request_id)
    db.commit()
    db.refresh(qc_run)

    return qc_run


@router.get("/requests/{request_id}/qc/results", response_model=List[QCResultOut])
def get_qc_results(
    request_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    req = db.get(Request, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    if user.role == "customer" and req.customer_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Берём последний run по id
    last_run = (
        db.query(QCRun)
        .filter(QCRun.request_id == request_id)
        .order_by(QCRun.id.desc())
        .first()
    )
    if not last_run:
        return []

    return (
        db.query(QCResult)
        .filter(QCResult.request_id == request_id, QCResult.qc_run_id == last_run.id)
        .order_by(QCResult.id.desc())
        .all()
    )
