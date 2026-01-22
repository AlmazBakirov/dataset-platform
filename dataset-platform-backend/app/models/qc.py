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

    status: Mapped[str] = mapped_column(
        String(32), default="done"
    )  # queued/running/done/failed
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
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
