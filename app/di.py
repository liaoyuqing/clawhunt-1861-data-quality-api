"""Composition root.

The API depends on a Composer that turns one DB session into a ready service. The
default composer talks to PostgreSQL and Redis; the test suite swaps in a composer
backed by an injectable caliber library and an in-memory cache.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cache.client import CacheClient, build_cache
from app.models.staff import Staff
from app.repositories.caliber_repo import (
    CachedCaliberProvider,
    CaliberDbProvider,
    CaliberProvider,
)
from app.repositories.crm_repo import CrmReader, SqlCrmReader
from app.services.data_quality import DataQualityService, StaffDirectory


class Composer(Protocol):
    def build(self, session: Session) -> DataQualityService: ...


class DbStaffDirectory:
    """Reads member-manager names from the CRM staff mirror.

    Kept as a standalone class (not a subclass of the frozen StaffDirectory
    dataclass) so it can hold a per-request cache.
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._cache: dict[uuid.UUID, str] = {}

    def name_of(self, staff_id: uuid.UUID | None) -> str:
        if staff_id is None:
            return "未分配"
        if staff_id in self._cache:
            return self._cache[staff_id]
        row = self._session.execute(select(Staff).where(Staff.id == staff_id)).scalar_one_or_none()
        name = row.name if row is not None else str(staff_id)
        self._cache[staff_id] = name
        return name


_shared_cache: CacheClient | None = None


def shared_cache() -> CacheClient:
    global _shared_cache
    if _shared_cache is None:
        _shared_cache = build_cache()
    return _shared_cache


class DbComposer:
    """Production wiring: PostgreSQL caliber + CRM mirror, Redis response cache."""

    def __init__(self, ttl_seconds: int = 60) -> None:
        self._ttl = ttl_seconds

    def build(self, session: Session) -> DataQualityService:
        return DataQualityService(
            crm=SqlCrmReader(session),
            caliber=CachedCaliberProvider(CaliberDbProvider(session)),
            cache=shared_cache(),
            staff=DbStaffDirectory(session),
            ttl_seconds=self._ttl,
        )


class StaticComposer:
    """Wiring used by tests and the offline demo: no database, no Redis."""

    def __init__(
        self,
        crm_reader: CrmReader,
        caliber: CaliberProvider,
        cache: CacheClient,
        staff_names: dict[uuid.UUID, str] | None = None,
        ttl_seconds: int = 60,
        now: datetime | None = None,
    ) -> None:
        self._crm = crm_reader
        self._caliber = caliber
        self._cache = cache
        self._staff = StaffDirectory(names=staff_names or {})
        self._ttl = ttl_seconds
        self._now = now

    @property
    def caliber(self) -> CaliberProvider:
        return self._caliber

    def build(self, session: Session) -> DataQualityService:
        return DataQualityService(
            crm=self._crm,
            caliber=self._caliber,
            cache=self._cache,
            staff=self._staff,
            ttl_seconds=self._ttl,
            now=self._now,
        )
