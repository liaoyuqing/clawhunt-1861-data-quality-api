"""AC1: overall and per-manager completeness must match the hand calculation.

The table printed by test_hand_calculation_table_is_reproducible is the same table
that appears in the delivery note, so a reviewer can check the numbers by eye.
"""

from __future__ import annotations

from tests import fixtures
from tests.conftest import Harness


def test_hand_calculation_table_is_reproducible(harness: Harness) -> None:
    print()
    print("enterprise    manager  filled/cells  ratio")
    for row in fixtures.hand_table():
        print(
            f"{row['enterprise']:<13} {row['manager']:<8} "
            f"{row['filled']:>2}/{row['cells']:<8} {row['ratio']:.4f}"
        )


def test_overall_completeness_matches_hand_calculation(harness: Harness) -> None:
    body = harness.get().json()
    data = body["data"]
    assert body["code"] == 0
    assert data["enterprise_count"] == 3
    assert data["field_count"] == 8
    assert (data["cell_filled"], data["cell_total"]) == (18, 24)
    assert data["completeness"] == 0.75
    assert data["target_pct"] == 95.0
    assert data["gap_to_target"] == 0.2


def test_manager_breakdown_matches_hand_calculation(harness: Harness) -> None:
    data = harness.get().json()["data"]
    by_name = {row["staff_name"]: row for row in data["managers"]}
    manager_a = by_name["会员经理甲"]
    manager_b = by_name["会员经理乙"]
    assert manager_a["enterprise_count"] == 2
    assert manager_a["completeness"] == 0.8125
    assert manager_a["gap_to_target"] == 0.1375
    assert manager_b["enterprise_count"] == 1
    assert manager_b["completeness"] == 0.625
    assert manager_b["gap_to_target"] == 0.325
    assert len(data["managers"]) == 2


def test_staff_filter_recomputes_against_that_manager(harness: Harness) -> None:
    data = harness.get(staff_id=str(fixtures.MANAGER_A)).json()["data"]
    assert data["staff_id"] == str(fixtures.MANAGER_A)
    assert data["enterprise_count"] == 2
    assert data["cell_total"] == 16
    assert data["cell_filled"] == 13
    assert data["completeness"] == 0.8125
    # Within manager A's scope, 云栖生物 sits at 6/8 = 0.75, below the 80% floor.
    assert data["low_completeness"] == [{"id": str(fixtures.E2), "name": "云栖生物"}]


def test_top_missing_fields_order_and_ties(harness: Harness) -> None:
    data = harness.get().json()["data"]
    gaps = data["top_missing_fields"]
    assert [row["field_key"] for row in gaps] == [
        "enterprise.track",
        "contact.decision_role",
        "contact.job_title",
        "enterprise.business_summary",
        "enterprise.stage",
    ]
    assert [row["missing"] for row in gaps] == [2, 1, 1, 1, 1]
    assert len(gaps) == 5


def test_single_empty_field_counts_every_enterprise(harness: Harness) -> None:
    data = harness.get().json()["data"]
    track = next(
        row for row in data["top_missing_fields"] if row["field_key"] == "enterprise.track"
    )
    assert track["missing"] == 2
    assert track["total"] == 3


def test_capability_card_completion_and_freshness(harness: Harness) -> None:
    cards = harness.get().json()["data"]["capability_cards"]
    assert cards["total"] == 3
    assert cards["confirmed"] == 2
    assert cards["completion_rate"] == 0.6667
    assert cards["fresh_confirmed"] == 1
    assert cards["freshness_rate"] == 0.3333
    assert cards["fresh_days"] == 90


def test_empty_site_returns_null_completeness_and_200() -> None:
    from app.cache.client import InMemoryCache
    from app.di import StaticComposer
    from app.main import create_app
    from app.repositories.caliber_repo import StaticCaliberProvider, build_default_versions
    from app.repositories.crm_repo import StubCrmReader
    from tests.auth import auth_header, make_token

    provider = StaticCaliberProvider(build_default_versions(), "v1")
    composer = StaticComposer(
        crm_reader=StubCrmReader({}),
        caliber=provider,
        cache=InMemoryCache(),
        now=fixtures.NOW,
    )
    app = create_app(composer=composer)
    token = make_token(org_id=fixtures.ORG_ID, site_ids=[fixtures.SITE_EMPTY])
    with TestClient(app) as client:
        response = client.get(
            "/api/dash/data-quality",
            params={"site_id": str(fixtures.SITE_EMPTY)},
            headers=auth_header(token),
        )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["completeness"] is None
    assert data["gap_to_target"] is None
    assert data["enterprise_count"] == 0
    assert data["cell_total"] == 0
    assert data["low_completeness"] == []
    assert data["managers"] == []
    assert data["capability_cards"]["completion_rate"] is None


from fastapi.testclient import TestClient  # noqa: E402  (used by the empty-site test)
