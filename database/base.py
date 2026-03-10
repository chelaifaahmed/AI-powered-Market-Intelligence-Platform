"""
database/base.py
----------------
Declarative base and shared timestamp mixin for all ORM models.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


class TimestampMixin:
    """
    Adds created_at and updated_at timestamps to any model.
    updated_at is automatically refreshed on every UPDATE via onupdate.
    """
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """
    Adds a deleted_at field for soft-delete support.
    A non-NULL value means the record is logically deleted.
    """
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()
