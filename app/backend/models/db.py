"""SQLAlchemy Base, UtcDateTime type, and utcnow helper."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class UtcDateTime(DateTime):
    """DateTime type that stores UTC-aware timestamps."""

    def __init__(self) -> None:
        super().__init__(timezone=True)


def utcnow() -> datetime:
    """Return the current UTC-aware datetime."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    type_annotation_map = {
        uuid.UUID: Uuid,
    }