"""Seed the fictional demo dataset into PostgreSQL.

Usage:
    DQ_DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:55433/dq1861 \
        python scripts/seed_demo.py

The script is idempotent: rows are upserted by primary key, and both caliber
versions are written so the dashboard can be flipped between v1 and v2 by
flipping the is_active flag (see scripts/set_caliber_version.py).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select

from app.db import get_session_factory
from app.models.caliber import CaliberFieldVersion
from app.models.staff import Staff
from app.repositories.caliber_repo import build_default_versions
from tests import fixtures


def _shift_cards(cards: list[object]) -> list[object]:
    """Move the fixture confirmation dates so they stay meaningful over time.

    The fixtures use fixed dates around 2026-03-01, which is what the hand
    calculation in the AC1 test is built on. In a live database those dates would
    soon fall outside the 90-day freshness window, so the seeded demo shifts the
    whole set by the same offset: the fresh/expired split stays 1 fresh, 1 stale
    and 1 unconfirmed, whatever day the demo is run on.
    """
    from datetime import UTC, datetime

    reference = fixtures.NOW
    offset = datetime.now(UTC) - reference
    shifted: list[object] = []
    for card in cards:
        confirmed = card.confirmed_at  # type: ignore[attr-defined]
        card.confirmed_at = confirmed + offset if confirmed is not None else None  # type: ignore[attr-defined]
        card.created_at = card.created_at + offset  # type: ignore[attr-defined]
        card.updated_at = card.updated_at + offset  # type: ignore[attr-defined]
        shifted.append(card)
    return shifted


def main() -> int:
    session = get_session_factory()()
    try:
        for model in (
            CaliberFieldVersion,
            Staff,
        ):
            session.execute(delete(model))
        from app.models.crm import CapabilityCard, Contact, Enterprise

        for model in (CapabilityCard, Contact, Enterprise):
            session.execute(delete(model))
        session.flush()

        session.add_all(
            [
                Staff(
                    id=fixtures.MANAGER_A,
                    org_id=fixtures.ORG_ID,
                    site_id=fixtures.SITE_ID,
                    name="会员经理甲",
                    role="member_manager",
                    created_at=fixtures.NOW,
                    updated_at=fixtures.NOW,
                ),
                Staff(
                    id=fixtures.MANAGER_B,
                    org_id=fixtures.ORG_ID,
                    site_id=fixtures.SITE_ID,
                    name="会员经理乙",
                    role="member_manager",
                    created_at=fixtures.NOW,
                    updated_at=fixtures.NOW,
                ),
            ]
        )
        session.add_all(fixtures.build_enterprises())
        session.add_all(fixtures.build_contacts())
        session.add_all(_shift_cards(fixtures.build_cards()))
        session.flush()

        for version, snapshot in build_default_versions().items():
            session.add(
                CaliberFieldVersion(
                    id=__import__("uuid").uuid5(
                        __import__("uuid").NAMESPACE_DNS, "1861.caliber." + version
                    ),
                    org_id=fixtures.ORG_ID,
                    site_id=fixtures.SITE_ID,
                    version=snapshot.version,
                    fields=list(snapshot.fields),
                    labels=dict(snapshot.labels),
                    target_pct=snapshot.target_pct,
                    low_pct=snapshot.low_pct,
                    fresh_days=snapshot.fresh_days,
                    calc_refs=list(snapshot.calc_refs),
                    is_active=version == "v2",
                    published_at=snapshot.published_at,
                    created_at=fixtures.NOW,
                    updated_at=fixtures.NOW,
                )
            )
        session.commit()

        counts = {
            "enterprises": len(
                session.execute(select(Enterprise).where(Enterprise.site_id == fixtures.SITE_ID))
                .scalars()
                .all()
            ),
            "caliber_versions": len(session.execute(select(CaliberFieldVersion)).scalars().all()),
            "active_version": session.execute(
                select(CaliberFieldVersion.version).where(CaliberFieldVersion.is_active.is_(True))
            ).scalar_one(),
        }
        print("SEEDED", counts)
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
