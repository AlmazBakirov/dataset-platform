from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"), index=True)
    assigned_to: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    status: Mapped[str] = mapped_column(
        String(30), default="open"
    )  # open/in_progress/done

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    images = relationship(
        "TaskImage", back_populates="task", cascade="all, delete-orphan"
    )


class TaskImage(Base):
    __tablename__ = "task_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    image_id: Mapped[int] = mapped_column(ForeignKey("images.id"), index=True)

    task = relationship("Task", back_populates="images")
