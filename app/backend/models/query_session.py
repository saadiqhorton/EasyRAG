"""QuerySession ORM model."""

import uuid
from datetime import datetime

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, UtcDateTime, utcnow


class QuerySession(Base):
    __tablename__ = "query_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(
        nullable=False, index=True
    )
    raw_query: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_query: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=utcnow
    )

    answers: Mapped[list["AnswerRecord"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )