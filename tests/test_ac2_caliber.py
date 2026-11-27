"""AC2: the field list comes from the caliber library, so a new version changes results.

v1 scores eight fields: 3 enterprises x 8 = 24 cells, 6 missing => 18/24 = 0.75.
v2 drops 赛道: the column disappears for all three enterprises (24 - 3 = 21 cells),
and of those three track cells only 星澜科技 had one filled, so filled drops to 17
and missing drops to 4 => 17/21 = 0.809523 => 0.8095. Switching the version also
changes the cache key, so a stale v1 payload can never be served under v2.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.cache.client import InMemoryCache
from app.cache.keys import data_quality_key
from app.di import StaticComposer
from app.main import create_app
from app.repositories.caliber_repo import (
    CachedCaliberProvider,
    CaliberSnapshot,
    StaticCaliberProvider,
    build_default_versions,
)
from app.repositories.crm_repo import StubCrmReader
from tests import fixtures
from tests.auth import auth_header, make_token
from tests.conftest import Harness


def _v2(harness: Harness) -> CaliberSnapshot:
    return build_default_versions()["v2"]


def test_v1_scores_eight_fields(harness: Harness) -> None:
    data = harness.get().json()["data"]
    assert data["caliber_version"] == "v1"
    assert data["field_count"] == 8
    assert data["completeness"] == 0.75


def test_v2_drops_track_and_changes_completeness(harness: Harness) -> None:
    harness.caliber.set_active("v2")
    data = harness.get().json()["data"]
    assert data["caliber_version"] == "v2"
    assert data["field_count"] == 7
    assert (data["cell_filled"], data["cell_total"]) == (17, 21)
    assert data["completeness"] == 0.8095
    assert data["gap_to_target"] == 0.1405
    # 赛道 is gone from the field-gap ranking because it is no longer scored, and with
    # only four fields still carrying gaps the top-five list itself shrinks to four.
    keys = [row["field_key"] for row in data["top_missing_fields"]]
    assert "enterprise.track" not in keys
    assert len(keys) == 4
    assert [row["missing"] for row in data["top_missing_fields"]] == [1, 1, 1, 1]


def test_field_count_follows_the_caliber_version(harness: Harness) -> None:
    counts = []
    for version in ("v1", "v2", "v1"):
        harness.caliber.set_active(version)
        counts.append(harness.get().json()["data"]["field_count"])
    assert counts == [8, 7, 8]


def test_cache_key_contains_version_and_misses_after_switch(harness: Harness) -> None:
    first = harness.get().json()["data"]
    assert first["cache_hit"] is False
    second = harness.get().json()["data"]
    assert second["cache_hit"] is True
    assert second["completeness"] == first["completeness"]

    harness.caliber.set_active("v2")
    after = harness.get().json()["data"]
    assert after["cache_hit"] is False, "v2 must not reuse the v1 cache entry"
    assert after["caliber_version"] == "v2"
    assert after["completeness"] == 0.8095

    v1_key = data_quality_key(str(fixtures.SITE_ID), None, "v1")
    v2_key = data_quality_key(str(fixtures.SITE_ID), None, "v2")
    assert v1_key == f"dash:dq:{fixtures.SITE_ID}:*:v1"
    assert v1_key != v2_key
    assert harness.cache.get_json(v1_key)["completeness"] == 0.75
    assert harness.cache.get_json(v2_key)["completeness"] == 0.8095


def test_rollback_to_previous_version_restores_old_numbers(harness: Harness) -> None:
    v1_first = harness.get().json()["data"]["completeness"]
    harness.caliber.set_active("v2")
    assert harness.get().json()["data"]["completeness"] != v1_first
    harness.caliber.set_active("v1")
    assert harness.get().json()["data"]["completeness"] == v1_first


def test_version_is_read_per_request_not_cached_in_the_app(harness: Harness) -> None:
    seen = []
    for _ in range(3):
        seen.append(harness.get().json()["data"]["caliber_version"])
        harness.caliber.set_active("v2" if seen[-1] == "v1" else "v1")
    assert seen == ["v1", "v2", "v1"]


def test_empty_caliber_field_list_returns_422(harness: Harness) -> None:
    empty = CaliberSnapshot(
        version="v3-empty",
        fields=(),
        labels={},
        target_pct=95.0,
        low_pct=80.0,
        fresh_days=90,
    )
    harness.caliber.add_version(empty)
    response = harness.get()
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == 42201
    assert body["message"] == "FIELD_LIST_EMPTY"


def test_unknown_field_key_in_caliber_rejected(harness: Harness) -> None:
    broken = replace(
        build_default_versions()["v1"],
        version="v4-broken",
        fields=("enterprise.industry", "nope.nope"),
    )
    harness.caliber.add_version(broken)
    with pytest.raises(LookupError):
        harness.get()


def test_stale_fallback_when_caliber_store_degrades() -> None:
    base = StaticCaliberProvider(build_default_versions(), "v1")

    class Flaky:
        def __init__(self) -> None:
            self.calls = 0

        def active(self, site_id: str) -> CaliberSnapshot:
            self.calls += 1
            if self.calls == 1:
                return base.active(site_id)
            raise RuntimeError("caliber store timeout")

    wrapped = CachedCaliberProvider(Flaky())
    provider = StaticCaliberProvider(build_default_versions(), "v1")
    composer = StaticComposer(
        crm_reader=StubCrmReader({fixtures.SITE_ID: fixtures.build_bundle()}),
        caliber=wrapped,
        cache=InMemoryCache(),
        staff_names={fixtures.MANAGER_A: "会员经理甲"},
        now=fixtures.NOW,
    )
    app = create_app(composer=composer)
    token = make_token(org_id=fixtures.ORG_ID, site_ids=[fixtures.SITE_ID])
    client = TestClient(app)
    first = client.get(
        "/api/dash/data-quality",
        params={"site_id": str(fixtures.SITE_ID)},
        headers=auth_header(token),
    ).json()["data"]
    # A different staff id means a different cache key, so the second call really
    # re-enters the service and hits the degraded caliber store.
    second = client.get(
        "/api/dash/data-quality",
        params={"site_id": str(fixtures.SITE_ID), "staff_id": str(fixtures.MANAGER_B)},
        headers=auth_header(token),
    ).json()["data"]
    assert first["stale"] is False
    assert second["stale"] is True
    assert second["caliber_version"] == first["caliber_version"]
    assert provider.active(str(fixtures.SITE_ID)).version == "v1"


def test_db_provider_reads_active_version_from_postgres(db_session) -> None:
    from app.repositories.caliber_repo import CaliberDbProvider

    snapshot = CaliberDbProvider(db_session).active(str(fixtures.SITE_ID))
    assert snapshot.version == "v2"
    assert len(snapshot.fields) == 7
    assert snapshot.target_pct == 95.0
    assert "compute_completeness" in snapshot.calc_refs
