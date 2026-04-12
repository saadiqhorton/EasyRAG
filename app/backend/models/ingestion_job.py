"""IngestionJob ORM model."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, UtcDateTime, utcnow


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), default="queued", nullable=False, index=True
    )
    current_stage: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=utcnow, index=True
    )

    collection: Mapped["Collection"] = relationship(
        back_populates="ingestion_jobs"
    )
    version: Mapped["DocumentVersion"] = relationship(
        back_populates="ingestion_jobs"
    )
    failure_events: Mapped[list["FailureEvent"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )