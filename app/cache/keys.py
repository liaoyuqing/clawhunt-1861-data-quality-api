"""Cache key layout.

The caliber version is part of the key: publishing v2 must never serve v1 scores.
"""

from __future__ import annotations


def data_quality_key(site_id: str, staff_id: str | None, caliber_version: str) -> str:
    return f"dash:dq:{site_id}:{staff_id or '*'}:{caliber_version}"
