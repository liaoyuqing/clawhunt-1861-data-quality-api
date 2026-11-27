"""Metric-caliber (口径库) library.

The dashboard never hard-codes the field list: the active caliber version is read
from this table on every request, so publishing a new version changes the numbers
without a redeploy.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import AuditMixin


class CaliberFieldVersion(Base, AuditMixin):
    __tablename__ = "caliber_field_versions"

    #: Monotonic version label, e.g. v1 / v2. Only one row per site is active.
    version: Mapped[str] = mapped_column(String(16), nullable=False)
    #: Ordered list of field keys, e.g. ["enterprise.industry", ...].
    fields: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    #: Human readable label per field key, used by the OpenAPI examples.
    labels: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False, default=dict)
    target_pct: Mapped[float] = mapped_column(Float, nullable=False, default=95.0)
    low_pct: Mapped[float] = mapped_column(Float, nullable=False, default=80.0)
    fresh_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    #: White-listed calculation names this version binds to (app.calc.registry).
    calc_refs: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = ["CaliberFieldVersion"]
