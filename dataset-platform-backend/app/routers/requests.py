from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.deps import require_roles, get_current_user
from app.schemas.requests import CreateRequestIn, RequestOut
from app.models.request import Request
from app.models.user import User

router = APIRouter(prefix="/requests", tags=["requests"])


@router.post("", response_model=RequestOut)
def create_request(
    data: CreateRequestIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["customer"])),
):
    req = Request(
        customer_id=user.id,
        title=data.title,
        description=data.description,
        classes=data.classes,
        status="draft",
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return {
        "id": str(req.id),
        "title": req.title,
        "description": req.description or "",
        "classes": req.classes or [],
        "status": req.status,
    }


@router.get("", response_model=list[RequestOut])
def list_requests(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Request)
    if user.role == "customer":
        q = q.filter(Request.customer_id == user.id)
    items = q.order_by(Request.id.desc()).all()
    return [
        {
            "id": str(r.id),
            "title": r.title,
            "description": r.description or "",
            "classes": r.classes or [],
            "status": r.status,
        }
        for r in items
    ]
