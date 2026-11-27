"""Pure calculation functions for the data-quality dashboard.

Everything in this module is side-effect free: it takes already-loaded rows and
returns numbers, which is what makes the hand calculation in the tests possible.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.calc.registry import register
from app.domain.fields import FieldSpec, is_filled, read_cell
from app.models.crm import CapabilityCard, Contact, Enterprise

FOUR_PLACES = Decimal("0.0001")


def round_ratio(value: float | None) -> float | None:
    """Round to 4 decimals with half-up, the dashboard display precision."""
    if value is None:
        return None
    return float(Decimal(str(value)).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP))


@dataclass(frozen=True, slots=True)
class EnterpriseRow:
    """One enterprise with its already-selected primary contact."""

    enterprise: Enterprise
    contact: Contact | None


@dataclass(frozen=True, slots=True)
class FieldGapRow:
    field_key: str
    label: str
    missing: int
    total: int


@dataclass(frozen=True, slots=True)
class CompletenessResult:
    enterprise_count: int
    field_count: int
    cell_total: int
    cell_filled: int
    completeness: float | None

    def gap_to(self, target_pct: float) -> float | None:
        if self.completeness is None:
            return None
        return round_ratio(target_pct / 100.0 - self.completeness)


def _score(rows: list[EnterpriseRow], specs: list[FieldSpec]) -> tuple[int, int, float | None]:
    cell_total = len(rows) * len(specs)
    if cell_total == 0:
        return 0, 0, None
    cell_filled = 0
    for row in rows:
        for spec in specs:
            if is_filled(read_cell(row.enterprise, row.contact, spec)):
                cell_filled += 1
    return cell_total, cell_filled, cell_filled / cell_total


@register("compute_completeness")
def compute_completeness(rows: list[EnterpriseRow], specs: list[FieldSpec]) -> CompletenessResult:
    """Overall completeness = filled cells / (enterprises * fields).

    Returns completeness=None (never NaN, never ZeroDivisionError) when the site
    has no enterprise at all.
    """
    cell_total, cell_filled, ratio = _score(rows, specs)
    return CompletenessResult(
        enterprise_count=len(rows),
        field_count=len(specs),
        cell_total=cell_total,
        cell_filled=cell_filled,
        completeness=round_ratio(ratio),
    )


@register("compute_manager_breakdown")
def compute_manager_breakdown(
    rows: list[EnterpriseRow], specs: list[FieldSpec]
) -> dict[uuid.UUID | None, CompletenessResult]:
    """Per member-manager completeness, computed over that manager's own rows."""
    grouped: dict[uuid.UUID | None, list[EnterpriseRow]] = {}
    for row in rows:
        grouped.setdefault(row.enterprise.owner_staff_id, []).append(row)
    return {staff_id: compute_completeness(group, specs) for staff_id, group in grouped.items()}


@register("compute_field_gaps")
def compute_field_gaps(rows: list[EnterpriseRow], specs: list[FieldSpec]) -> list[FieldGapRow]:
    """Missing count per field.

    Ordering: missing desc, then field key asc, so ties are stable across runs.
    """
    gaps: list[FieldGapRow] = []
    for spec in specs:
        missing = sum(
            1 for row in rows if not is_filled(read_cell(row.enterprise, row.contact, spec))
        )
        gaps.append(
            FieldGapRow(field_key=spec.key, label=spec.label, missing=missing, total=len(rows))
        )
    gaps.sort(key=lambda gap: (-gap.missing, gap.field_key))
    return gaps


def is_below_threshold(ratio: float, threshold: float) -> bool:
    """True when a completeness ratio is strictly below the low threshold.

    The comparison is strict on purpose: a record at exactly 80.00% is NOT below
    the threshold and stays out of the list, while a record at 79.99% is in.
    """
    return ratio < threshold


@register("compute_low_completeness")
def compute_low_completeness(
    rows: list[EnterpriseRow], specs: list[FieldSpec], low_pct: float
) -> list[tuple[Enterprise, float]]:
    """Enterprises strictly below the low threshold, ascending by completeness.

    A record at exactly 80.00% is NOT below the threshold and stays out; a record
    at 79.99% is in. Ties are broken by id so the page is deterministic.
    """
    threshold = low_pct / 100.0
    scored: list[tuple[Enterprise, float]] = []
    for row in rows:
        _total, _filled, ratio = _score([row], specs)
        if ratio is None:
            continue
        ratio = round_ratio(ratio)
        assert ratio is not None
        if is_below_threshold(ratio, threshold):
            scored.append((row.enterprise, ratio))
    scored.sort(key=lambda item: (item[1], str(item[0].id)))
    return scored


@register("capability_card_stats")
def capability_card_stats(
    cards: list[CapabilityCard], fresh_days: int, now: datetime
) -> dict[str, int | float | None]:
    """Completion rate plus freshness = share confirmed inside the fresh window."""
    total = len(cards)
    confirmed = sum(1 for card in cards if card.confirmed_at is not None)
    cutoff = now - timedelta(days=fresh_days)
    fresh = sum(
        1
        for card in cards
        if card.confirmed_at is not None and _as_utc(card.confirmed_at) >= cutoff
    )
    return {
        "total": total,
        "confirmed": confirmed,
        "completion_rate": round_ratio(confirmed / total) if total else None,
        "fresh_confirmed": fresh,
        "freshness_rate": round_ratio(fresh / total) if total else None,
        "fresh_days": fresh_days,
    }


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
