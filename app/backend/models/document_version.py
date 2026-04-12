"""DocumentVersion ORM model."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import Index, UniqueConstraint

from .db import Base, UtcDateTime, utcnow


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )
    storage_key: Mapped[str] = mapped_column(
        String(1024), nullable=False
    )
    parse_confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    index_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=utcnow
    )

    document: Mapped["SourceDocument"] = relationship(
        back_populates="versions"
    )
    derived_assets: Mapped[list["DerivedAsset"]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )
    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(
        back_populates="version"
    )

    __table_args__ = (
        UniqueConstraint(
            "document_id", "version_number", name="uq_document_version"
        ),
        Index("ix_document_versions_active", "document_id", "is_active"),
    )