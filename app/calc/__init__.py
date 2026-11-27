"""Registered calculation functions.

Every metric is registered here by name; the caliber library references these
names through its calc_ref column, so a new caliber version can pick a different
implementation without touching the API layer.
"""

from app.calc.completeness import (
    capability_card_stats,
    compute_completeness,
    compute_field_gaps,
    compute_low_completeness,
)
from app.calc.registry import CALC_REGISTRY, register, resolve_calc

__all__ = [
    "CALC_REGISTRY",
    "capability_card_stats",
    "compute_completeness",
    "compute_field_gaps",
    "compute_low_completeness",
    "register",
    "resolve_calc",
]
