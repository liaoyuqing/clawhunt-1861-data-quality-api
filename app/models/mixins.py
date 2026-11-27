"""Shared column mixins.

Every business table in this project carries the platform-wide audit columns:
id (UUID primary key), org_id, site_id, created_at, created_by, updated_at and
deleted_at (soft delete).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(UTC)


class UuidPkMixin:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class SiteScopedMixin(UuidPkMixin):
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)


class AuditMixin(SiteScopedMixin):
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_utcnow
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class IdentityNameMixin:
    """Display name plus the two columns that must never leak through the API."""

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    uscc: Mapped[str | None] = mapped_column(String(32), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
