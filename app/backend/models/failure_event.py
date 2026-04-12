"""FailureEvent ORM model."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, UtcDateTime, utcnow


class FailureEvent(Base):
    __tablename__ = "failure_events"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ingestion_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(
        nullable=False, index=True
    )
    stage_name: Mapped[str] = mapped_column(String(30), nullable=False)
    error_type: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_retryable: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    suggested_action: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=utcnow, index=True
    )

    job: Mapped["IngestionJob"] = relationship(
        back_populates="failure_events"
    )