from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.annotation import Annotation
from app.models.request import Request
from app.models.task import Task, TaskImage
from app.schemas.annotations import SaveLabelsIn, SaveLabelsOut
from app.schemas.tasks import TaskDetailOut, TaskImageOut, TaskListOut

router = APIRouter(prefix="", tags=["tasks"])


def _image_url(image_id: int) -> str:
    """
    Возвращаем URL для UI.
    Лучше относительный путь, чтобы UI сам подставлял BACKEND_URL.
    """
    return f"/images/{image_id}/content"


def _require_task_access(task: Task, user) -> None:
    """
    RBAC для задач:
    - labeler: только свои задачи (assigned_to == user.id)
    - admin/universal: все задачи
    - остальные: запрещено
    """
    if user.role not in ("labeler", "admin", "universal"):
        raise HTTPException(status_code=403, detail="Forbidden")

    if user.role == "labeler" and task.assigned_to != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")


def _effective_labeler_id(task: Task, user) -> int:
    """
    Кто считается labeler-ом для записи/подсчёта прогресса:
    - если пользователь labeler -> он сам
    - если admin/universal -> assigned_to (чтобы админ мог тестить через Swagger,
      но запись шла как назначенный разметчик)
    """
    if user.role == "labeler":
        return int(user.id)

    # admin/universal
    if task.assigned_to is None:
        raise HTTPException(status_code=400, detail="Task has no assigned labeler")
    return int(task.assigned_to)


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

    _require_task_access(task, user)

    req = db.get(Request, task.request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    images_out: List[TaskImageOut] = []
    # task.images — relationship к TaskImage (task_images)
    for ti in getattr(task, "images", []) or []:
        images_out.append(
            TaskImageOut(image_id=ti.image_id, url=_image_url(ti.image_id))
        )

    return TaskDetailOut(
        id=task.id,
        title=req.title,
        request_id=task.request_id,
        status=task.status,
        classes=req.classes or [],
        images=images_out,
    )


@router.get("/tasks/{task_id}/progress")
def get_task_progress(
    task_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    _require_task_access(task, user)
    eff_labeler_id = _effective_labeler_id(task, user)

    total_images = (
        db.query(func.count(TaskImage.id)).filter(TaskImage.task_id == task_id).scalar()
        or 0
    )

    labeled_images = (
        db.query(func.count(distinct(Annotation.image_id)))
        .filter(
            Annotation.task_id == task_id,
            Annotation.labeler_id == eff_labeler_id,
        )
        .scalar()
        or 0
    )

    remaining_images = max(int(total_images) - int(labeled_images), 0)

    return {
        "task_id": task_id,
        "total_images": int(total_images),
        "labeled_images": int(labeled_images),
        "remaining_images": int(remaining_images),
    }


@router.post("/tasks/{task_id}/annotations", response_model=SaveLabelsOut)
@router.post("/tasks/{task_id}/labels", response_model=SaveLabelsOut)
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

    if user.role == "labeler" and task.assigned_to != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    eff_labeler_id = _effective_labeler_id(task, user)

    # Проверим, что image_id принадлежит задаче
    ti = (
        db.query(TaskImage)
        .filter(TaskImage.task_id == task_id, TaskImage.image_id == payload.image_id)
        .first()
    )
    if not ti:
        raise HTTPException(status_code=400, detail="image_id is not in this task")

    # labels по стандарту list[str]
    labels = payload.labels

    # Upsert: (task_id, image_id, eff_labeler_id)
    ann = (
        db.query(Annotation)
        .filter(
            Annotation.task_id == task_id,
            Annotation.image_id == payload.image_id,
            Annotation.labeler_id == eff_labeler_id,
        )
        .first()
    )

    if ann:
        ann.labels = labels
    else:
        ann = Annotation(
            task_id=task_id,
            image_id=payload.image_id,
            labeler_id=eff_labeler_id,
            labels=labels,
        )
        db.add(ann)

    # Если задача была open — переведём в in_progress при первой разметке
    if getattr(task, "status", None) == "open":
        task.status = "in_progress"

    db.commit()
    db.refresh(ann)

    return SaveLabelsOut(
        status=task.status,
        task_id=task_id,
        image_id=payload.image_id,
        labeler_id=eff_labeler_id,
        labels=labels,
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

    _require_task_access(task, user)

    # идемпотентность
    if task.status == "done":
        return {"ok": True, "task_id": task_id, "status": task.status}

    eff_labeler_id = _effective_labeler_id(task, user)

    total_images = (
        db.query(func.count(TaskImage.id)).filter(TaskImage.task_id == task_id).scalar()
        or 0
    )

    if int(total_images) <= 0:
        raise HTTPException(status_code=409, detail="Task has no images")

    labeled_images = (
        db.query(func.count(distinct(Annotation.image_id)))
        .filter(
            Annotation.task_id == task_id,
            Annotation.labeler_id == eff_labeler_id,
        )
        .scalar()
        or 0
    )

    # Главная защита
    if int(labeled_images) < int(total_images):
        raise HTTPException(
            status_code=409,
            detail=f"Task is not fully labeled ({int(labeled_images)}/{int(total_images)})",
        )

    task.status = "done"
    db.commit()

    return {
        "ok": True,
        "task_id": task_id,
        "status": task.status,
        "labeled_images": int(labeled_images),
        "total_images": int(total_images),
    }
