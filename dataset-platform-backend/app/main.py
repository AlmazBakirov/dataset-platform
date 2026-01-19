from fastapi import FastAPI
from sqlalchemy.orm import Session
from app.db.session import Base, engine, SessionLocal
from app.models.user import User
from app.models.request import Request  # noqa: F401
from app.core.security import hash_password
from app.routers.auth import router as auth_router
from app.routers.requests import router as requests_router

app = FastAPI(title="Dataset Platform Backend")


@app.get("/health")
def health():
    return {"status": "ok"}


def seed_users(db: Session) -> None:
    seeds = [
        ("customer1", "pass", "customer"),
        ("labeler1", "pass", "labeler"),
        ("admin1", "pass", "admin"),
        ("universal1", "pass", "universal"),
    ]
    for username, pwd, role in seeds:
        exists = db.query(User).filter(User.username == username).first()
        if not exists:
            db.add(
                User(
                    username=username,
                    password_hash=hash_password(pwd),
                    role=role,
                    is_active=True,
                )
            )
    db.commit()


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_users(db)
    finally:
        db.close()


app.include_router(auth_router)
app.include_router(requests_router)
