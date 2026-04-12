"""Chunk ORM model."""

import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import Index

from .db import Base


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    section_path: Mapped[str | None] = mapped_column(
        String(1024), nullable=True
    )
    page_number_start: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    page_number_end: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    modality: Mapped[str] = mapped_column(
        String(20), default="text", nullable=False
    )
    confidence: Mapped[float] = mapped_column(
        Float, default=1.0, nullable=False
    )
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    text_content: Mapped[str] = mapped_column(Text, nullable=False)

    version: Mapped["DocumentVersion"] = relationship(
        back_populates="chunks"
    )

    __table_args__ = (
        Index("ix_chunks_collection_order", "collection_id", "order_index"),
        Index("ix_chunks_version", "version_id"),
    )