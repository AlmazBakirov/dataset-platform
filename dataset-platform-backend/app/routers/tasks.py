from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.task import Task, TaskImage
from app.models.request import Request
from app.models.annotation import Annotation
from app.schemas.tasks import TaskListOut, TaskDetailOut, TaskImageOut
from app.schemas.annotations import SaveLabelsIn, SaveLabelsOut

router = APIRouter(prefix="", tags=["tasks"])


def _image_url(image_id: int) -> str:
    # позже сделаем endpoint /images/{id}/content
    return f"http://127.0.0.1:8000/images/{image_id}/content"


@router.get("/tasks", response_model=List[TaskListOut])
def list_tasks(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if user.role not in ("labeler", "admin", "universal"):
        raise HTTPException(status_code=403, detail="Forbidden")

    q = db.query(Task).order_by(Task.id.desc())

    if user.role == "labeler":
        q = q.filter(Task.assigned_to == user.id)

    return q.all()


@router.get("/tasks/{task_id}", response_model=TaskDetailOut)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if user.role == "labeler" and task.assigned_to != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    req = db.get(Request, task.request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    # task_images -> список image_id
    rows = db.query(TaskImage).filter(TaskImage.task_id == task_id).all()
    image_ids = [r.image_id for r in rows]

    images_out: List[TaskImageOut] = []
    for iid in image_ids:
        images_out.append(TaskImageOut(image_id=iid, url=_image_url(iid)))

    return TaskDetailOut(
        id=task.id,
        title=req.title or f"Task {task.id}",
        request_id=task.request_id,
        status=task.status,
        classes=req.classes or [],
        images=images_out,
    )


@router.post("/tasks/{task_id}/annotations", response_model=SaveLabelsOut)
def save_labels(
    task_id: int,
    payload: SaveLabelsIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if user.role not in ("labeler", "admin", "universal"):
        raise HTTPException(status_code=403, detail="Forbidden")

    # labeler может править только свою задачу
    if user.role == "labeler" and task.assigned_to != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    # ВАЖНО: определяем, кого считаем "лейблером" для записи
    effective_labeler_id = user.id if user.role == "labeler" else task.assigned_to

    if effective_labeler_id is None:
        raise HTTPException(status_code=400, detail="Task has no assigned labeler")

    # Проверим, что image_id реально входит в task
    link = (
        db.query(TaskImage)
        .filter(TaskImage.task_id == task_id, TaskImage.image_id == payload.image_id)
        .first()
    )
    if not link:
        raise HTTPException(status_code=400, detail="Image not in this task")

    # upsert annotation (по effective_labeler_id)
    ann = (
        db.query(Annotation)
        .filter(
            Annotation.task_id == task_id,
            Annotation.image_id == payload.image_id,
            Annotation.labeler_id == effective_labeler_id,
        )
        .first()
    )

    if not ann:
        ann = Annotation(
            task_id=task_id,
            image_id=payload.image_id,
            labeler_id=effective_labeler_id,
            labels=payload.labels,
        )
        db.add(ann)
    else:
        ann.labels = payload.labels

    # поставить in_progress если было open
    if task.status == "open":
        task.status = "in_progress"

    db.commit()

    return SaveLabelsOut(
        ok=True,
        status=task.status,
        task_id=task_id,
        image_id=payload.image_id,
        labels=payload.labels,
    )


@router.post("/tasks/{task_id}/complete")
def complete_task(
    task_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if user.role == "labeler" and task.assigned_to != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    task.status = "done"
    db.commit()
    return {"ok": True, "task_id": task_id, "status": task.status}
