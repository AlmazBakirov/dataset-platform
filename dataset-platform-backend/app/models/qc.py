from datetime import datetime, timezone

from sqlalchemy import (
    Integer,
    String,
    ForeignKey,
    DateTime,
    Float,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class QCRun(Base):
    __tablename__ = "qc_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"), index=True)

    # NEW: связь с Celery job
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # FIX: правильный дефолт
    status: Mapped[str] = mapped_column(
        String(32), default="queued", index=True
    )  # queued/running/done/failed

    params: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # OPTIONAL but recommended: created_at отдельно, чтобы started_at был именно "когда реально стартовали"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # FIX: started_at не должен ставиться при создании (он будет ставиться в worker)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class QCResult(Base):
    __tablename__ = "qc_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    qc_run_id: Mapped[int] = mapped_column(ForeignKey("qc_runs.id"), index=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"), index=True)
    image_id: Mapped[int] = mapped_column(ForeignKey("images.id"), index=True)

    duplicate_score: Mapped[float] = mapped_column(Float, default=0.0)
    duplicate_of_image_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    ai_generated_score: Mapped[float] = mapped_column(Float, default=0.0)
    flags: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
