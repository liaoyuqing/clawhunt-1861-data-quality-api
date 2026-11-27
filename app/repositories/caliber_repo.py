"""Metric-caliber (口径库) reader.

Two sources are supported behind one protocol:

* CaliberDbProvider  - production: reads caliber_field_versions from PostgreSQL.
* StaticCaliberProvider - tests and offline demos: an injectable in-memory library.

The dashboard asks for the active version and the field list on every request, so
publishing a new version changes the numbers immediately.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.fields import get_field_spec
from app.models.caliber import CaliberFieldVersion

logger = logging.getLogger(__name__)


class CaliberError(RuntimeError):
    """Raised when the caliber library cannot serve a usable field list."""


class FieldListEmpty(CaliberError):
    """The active caliber version carries no field at all (maps to 422 FIELD_LIST_EMPTY)."""


class CaliberUnavailable(CaliberError):
    """The caliber library is unreachable and no cached copy is available."""


@dataclass(frozen=True, slots=True)
class CaliberSnapshot:
    version: str
    fields: tuple[str, ...]
    labels: dict[str, str]
    target_pct: float
    low_pct: float
    fresh_days: int
    calc_refs: tuple[str, ...] = field(default=("compute_completeness",))
    published_at: datetime | None = None

    def validate(self) -> CaliberSnapshot:
        if not self.fields:
            raise FieldListEmpty(self.version)
        for key in self.fields:
            get_field_spec(key)
        return self


class CaliberProvider(Protocol):
    def active(self, site_id: str) -> CaliberSnapshot: ...


class StaticCaliberProvider:
    """Injectable caliber library keyed by version, with an active version pointer."""

    def __init__(self, versions: dict[str, CaliberSnapshot], active_version: str) -> None:
        self._versions = dict(versions)
        self._active = active_version

    def active(self, site_id: str) -> CaliberSnapshot:
        return self._versions[self._active].validate()

    def set_active(self, version: str) -> None:
        self._active = version

    def add_version(self, snapshot: CaliberSnapshot, *, activate: bool = True) -> None:
        self._versions[snapshot.version] = snapshot
        if activate:
            self._active = snapshot.version


class CaliberDbProvider:
    """Reads the active version row for the requested site."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def active(self, site_id: str) -> CaliberSnapshot:
        import uuid as _uuid

        stmt = (
            select(CaliberFieldVersion)
            .where(
                CaliberFieldVersion.site_id == _uuid.UUID(str(site_id)),
                CaliberFieldVersion.is_active.is_(True),
                CaliberFieldVersion.deleted_at.is_(None),
            )
            .order_by(CaliberFieldVersion.published_at.desc().nullslast())
            .limit(1)
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        if row is None:
            raise FieldListEmpty(str(site_id))
        return CaliberSnapshot(
            version=row.version,
            fields=tuple(row.fields),
            labels=dict(row.labels),
            target_pct=row.target_pct,
            low_pct=row.low_pct,
            fresh_days=row.fresh_days,
            calc_refs=tuple(row.calc_refs),
            published_at=row.published_at,
        ).validate()


class CachedCaliberProvider:
    """Wraps a provider with the last known good snapshot.

    When the underlying caliber store throws, the most recent snapshot is served
    and the response is marked stale instead of failing the whole dashboard.
    """

    def __init__(self, inner: CaliberProvider) -> None:
        self._inner = inner
        self._last: CaliberSnapshot | None = None
        self._last_stale = False

    def active(self, site_id: str) -> CaliberSnapshot:
        try:
            snapshot = self._inner.active(site_id)
        except FieldListEmpty:
            raise
        except Exception as exc:
            if self._last is None:
                raise CaliberUnavailable(str(exc)) from exc
            logger.warning("caliber store degraded, serving cached %s", self._last.version)
            self._last_stale = True
            return self._last
        self._last = snapshot
        self._last_stale = False
        return snapshot

    @property
    def stale(self) -> bool:
        return self._last_stale


DEFAULT_FIELD_LIST: Sequence[str] = (
    "enterprise.industry",
    "enterprise.track",
    "enterprise.stage",
    "enterprise.registered_location",
    "enterprise.business_summary",
    "enterprise.owner_staff_id",
    "contact.job_title",
    "contact.decision_role",
)


def default_labels() -> dict[str, str]:
    return {key: get_field_spec(key).label for key in DEFAULT_FIELD_LIST}


def build_default_versions() -> dict[str, CaliberSnapshot]:
    """v1 = the eight fields in the brief; v2 drops 赛道 and keeps seven."""
    v1 = CaliberSnapshot(
        version="v1",
        fields=tuple(DEFAULT_FIELD_LIST),
        labels=default_labels(),
        target_pct=95.0,
        low_pct=80.0,
        fresh_days=90,
        calc_refs=("compute_completeness", "compute_manager_breakdown", "compute_field_gaps"),
        published_at=datetime(2026, 1, 5, tzinfo=UTC),
    )
    v2_fields = tuple(key for key in DEFAULT_FIELD_LIST if key != "enterprise.track")
    v2 = CaliberSnapshot(
        version="v2",
        fields=v2_fields,
        labels={key: get_field_spec(key).label for key in v2_fields},
        target_pct=95.0,
        low_pct=80.0,
        fresh_days=90,
        calc_refs=("compute_completeness", "compute_manager_breakdown", "compute_field_gaps"),
        published_at=datetime(2026, 2, 2, tzinfo=UTC),
    )
    return {"v1": v1, "v2": v2}
