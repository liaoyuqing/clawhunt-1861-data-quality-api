"""Response models for GET /api/dash/data-quality."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FieldGap(BaseModel):
    field_key: str = Field(description="Caliber-library field key, e.g. enterprise.track")
    label: str = Field(description="Human readable label of the field")
    missing: int = Field(description="Number of enterprises missing this field")
    total: int = Field(description="Number of enterprises evaluated for this field")


class ManagerRow(BaseModel):
    staff_id: str
    staff_name: str
    enterprise_count: int
    completeness: float | None = Field(
        default=None, description="null when the manager owns no enterprise in this site"
    )
    gap_to_target: float | None = None


class LowCompletenessEnterprise(BaseModel):
    """Projection is deliberately minimal: id and name only.

    No phone / uscc / contact data may ever be added to this model; the test suite
    asserts the exact key set of the serialised payload.
    """

    id: str
    name: str


class CapabilityCardStats(BaseModel):
    total: int
    confirmed: int
    completion_rate: float | None = None
    fresh_confirmed: int
    freshness_rate: float | None = None
    fresh_days: int


class DataQualityData(BaseModel):
    site_id: str
    staff_id: str | None = None
    caliber_version: str
    field_count: int
    enterprise_count: int
    cell_total: int
    cell_filled: int
    completeness: float | None = Field(
        default=None, description="Filled cells / total cells; null when there are no rows"
    )
    target_pct: float
    gap_to_target: float | None = Field(
        default=None, description="target_pct/100 - completeness, rounded to 4 decimals"
    )
    managers: list[ManagerRow]
    top_missing_fields: list[FieldGap]
    capability_cards: CapabilityCardStats
    low_completeness: list[LowCompletenessEnterprise]
    low_completeness_threshold_pct: float
    low_completeness_total: int
    stale: bool = Field(default=False, description="True when served from a degraded caliber cache")
    cache_hit: bool = False
