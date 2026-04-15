"""AnswerRecord ORM model."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, UtcDateTime, utcnow


class AnswerRecord(Base):
    __tablename__ = "answer_records"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("query_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(
        nullable=False, index=True
    )
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_mode: Mapped[str] = mapped_column(String(40), nullable=False)
    citations_json: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    raw_candidate_scores_json: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    evidence_json: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    reranker_used: Mapped[bool] = mapped_column(Boolean, nullable=False)
    llm_model: Mapped[str] = mapped_column(String(100), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=utcnow
    )

    session: Mapped["QuerySession"] = relationship(
        back_populates="answers"
    )