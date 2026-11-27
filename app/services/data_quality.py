"""Aggregation service behind GET /api/dash/data-quality.

Flow per request:
1. load the active caliber version (fields, thresholds) -> part of the cache key
2. read the CRM slice for the site (optionally one member manager)
3. run the registered calc functions
4. project the low-completeness list down to id + name only
5. cache the envelope payload for 60 seconds under a version-scoped key
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from app.cache.client import CacheClient
from app.cache.keys import data_quality_key
from app.calc.completeness import (
    CompletenessResult,
    EnterpriseRow,
    capability_card_stats,
    compute_completeness,
    compute_field_gaps,
    compute_low_completeness,
    round_ratio,
)
from app.calc.registry import resolve_calc
from app.domain.fields import FieldSpec, get_field_spec
from app.repositories.caliber_repo import CaliberProvider, CaliberSnapshot
from app.repositories.crm_repo import CrmReader, to_rows
from app.schemas.data_quality import (
    CapabilityCardStats,
    DataQualityData,
    FieldGap,
    LowCompletenessEnterprise,
    ManagerRow,
)

TOP_MISSING_FIELDS = 5


@dataclass(frozen=True, slots=True)
class StaffRef:
    id: uuid.UUID
    name: str


@dataclass(frozen=True, slots=True)
class StaffDirectory:
    """Minimal staff lookup; the real deployment reads crm_staff."""

    names: dict[uuid.UUID, str]

    def name_of(self, staff_id: uuid.UUID | None) -> str:
        if staff_id is None:
            return "未分配"
        return self.names.get(staff_id, str(staff_id))


class StaffNameResolver(Protocol):
    """Anything that can turn a member-manager id into a display name."""

    def name_of(self, staff_id: uuid.UUID | None) -> str: ...


class DataQualityService:
    def __init__(
        self,
        crm: CrmReader,
        caliber: CaliberProvider,
        cache: CacheClient,
        staff: StaffNameResolver,
        ttl_seconds: int = 60,
        now: datetime | None = None,
    ) -> None:
        self._crm = crm
        self._caliber = caliber
        self._cache = cache
        self._staff = staff
        self._ttl = ttl_seconds
        self._now = now

    def now(self) -> datetime:
        return self._now or datetime.now(UTC)

    def get(self, site_id: uuid.UUID, staff_id: uuid.UUID | None) -> DataQualityData:
        snapshot: CaliberSnapshot = self._caliber.active(str(site_id))
        # The caliber version binds its metrics through the white-listed registry;
        # a version referencing an unknown function fails loudly instead of silently
        # scoring with the wrong implementation.
        for calc_ref in snapshot.calc_refs:
            resolve_calc(calc_ref)
        key = data_quality_key(str(site_id), str(staff_id) if staff_id else None, snapshot.version)
        hit = self._cache.get_json(key)
        if hit is not None:
            payload = DataQualityData.model_validate(hit)
            payload.cache_hit = True
            return payload

        data = self._compute(site_id, staff_id, snapshot)
        self._cache.set_json(key, data.model_dump(mode="json"), self._ttl)
        return data

    def _compute(
        self, site_id: uuid.UUID, staff_id: uuid.UUID | None, snapshot: CaliberSnapshot
    ) -> DataQualityData:
        bundle = self._crm.load(site_id, staff_id)
        rows = to_rows(bundle)
        specs = [get_field_spec(key) for key in snapshot.fields]

        overall: CompletenessResult = compute_completeness(rows, specs)
        managers = self._manager_rows(rows, specs, snapshot)
        # Only fields that actually carry a gap are useful on the panel; the list is
        # truncated to five after that filter, so a short list means few real gaps.
        gaps = [gap for gap in compute_field_gaps(rows, specs) if gap.missing > 0][
            :TOP_MISSING_FIELDS
        ]
        low = compute_low_completeness(rows, specs, snapshot.low_pct)
        cards = capability_card_stats(bundle.cards, snapshot.fresh_days, self.now())

        return DataQualityData(
            site_id=str(site_id),
            staff_id=str(staff_id) if staff_id else None,
            caliber_version=snapshot.version,
            field_count=len(specs),
            enterprise_count=overall.enterprise_count,
            cell_total=overall.cell_total,
            cell_filled=overall.cell_filled,
            completeness=overall.completeness,
            target_pct=snapshot.target_pct,
            gap_to_target=overall.gap_to(snapshot.target_pct),
            managers=managers,
            top_missing_fields=[
                FieldGap(field_key=g.field_key, label=g.label, missing=g.missing, total=g.total)
                for g in gaps
            ],
            capability_cards=CapabilityCardStats(
                total=int(cards["total"] or 0),
                confirmed=int(cards["confirmed"] or 0),
                completion_rate=_opt_float(cards["completion_rate"]),
                fresh_confirmed=int(cards["fresh_confirmed"] or 0),
                freshness_rate=_opt_float(cards["freshness_rate"]),
                fresh_days=int(cards["fresh_days"] or snapshot.fresh_days),
            ),
            low_completeness=[
                LowCompletenessEnterprise(id=str(enterprise.id), name=enterprise.name)
                for enterprise, _ratio in low
            ],
            low_completeness_threshold_pct=snapshot.low_pct,
            low_completeness_total=len(low),
            stale=self._caliber_stale(),
        )

    def _manager_rows(
        self, rows: list[EnterpriseRow], specs: list[FieldSpec], snapshot: CaliberSnapshot
    ) -> list[ManagerRow]:
        grouped: dict[uuid.UUID | None, list[EnterpriseRow]] = {}
        for row in rows:
            grouped.setdefault(row.enterprise.owner_staff_id, []).append(row)
        result: list[ManagerRow] = []
        for owner, group in sorted(grouped.items(), key=lambda item: str(item[0] or "")):
            stats = compute_completeness(group, specs)
            result.append(
                ManagerRow(
                    staff_id=str(owner) if owner else "",
                    staff_name=self._staff.name_of(owner),
                    enterprise_count=stats.enterprise_count,
                    completeness=stats.completeness,
                    gap_to_target=stats.gap_to(snapshot.target_pct),
                )
            )
        return result

    def _caliber_stale(self) -> bool:
        return bool(getattr(self._caliber, "stale", False))


def _opt_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return round_ratio(float(value))
    return round_ratio(float(str(value)))
