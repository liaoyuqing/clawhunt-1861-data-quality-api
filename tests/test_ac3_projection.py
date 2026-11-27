"""AC3: the below-80% list must expose exactly the keys id and name.

The assertion is a set equality on the serialised keys, plus an explicit scan for
the sensitive columns that exist in the CRM mirror (phone, uscc, contact data).

The 12-enterprise fixture below is generated from an explicit "filled cells" count
per enterprise, so the expected below-80% set can be derived by hand:

    filled cells / 8 = completeness,  below 80%  <=>  filled <= 6
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient

from app.cache.client import InMemoryCache
from app.di import StaticComposer
from app.main import create_app
from app.models.crm import CapabilityCard, Contact, Enterprise
from app.repositories.caliber_repo import (
    CaliberSnapshot,
    StaticCaliberProvider,
    build_default_versions,
)
from app.repositories.crm_repo import CrmBundle, StubCrmReader
from tests import fixtures
from tests.auth import auth_header, make_token

NOW = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
SITE = uuid.UUID("55555555-5555-4555-8555-555555555555")
OWNER = fixtures.MANAGER_A
FORBIDDEN_KEYS = (
    "contact_phone",
    "uscc",
    "phone",
    "registered_location",
    "business_summary",
    "industry",
    "track",
    "stage",
    "job_title",
    "decision_role",
)
SENSITIVE_VALUES = (fixtures.FAKE_PHONE, fixtures.FAKE_USCC)

#: (name, filled enterprise fields, job_title filled?, decision_role filled?)
#: The 8 scored fields of caliber v1: 6 enterprise-level, 2 contact-level.
CASES: list[tuple[str, int, bool, bool]] = [
    ("星澜科技", 6, True, True),  # 8/8 = 1.0000
    ("云栖生物", 6, True, False),  # 7/8 = 0.8750
    ("恒泰智造", 6, False, False),  # 6/8 = 0.7500  <- below
    ("联川新材", 5, True, False),  # 6/8 = 0.7500  <- below
    ("瀚海装备", 5, False, False),  # 5/8 = 0.6250  <- below
    ("青禾农业", 1, False, False),  # 1/8 = 0.1250  <- below
    ("远望能源", 6, True, True),  # 8/8 = 1.0000
    ("晨星材料", 3, True, True),  # 5/8 = 0.6250  <- below
]


def _case_ids(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, "1861.demo." + name)


def _build_case(
    name: str, enterprise_filled: int, job_title: bool, decision_role: bool
) -> Enterprise:
    attributes = ["industry", "track", "stage", "registered_location", "business_summary"]
    values: dict[str, Any] = {key: f"{name}-{key}" for key in attributes}
    slots: list[tuple[str, Any]] = [
        ("industry", values["industry"]),
        ("track", values["track"]),
        ("stage", values["stage"]),
        ("registered_location", values["registered_location"]),
        ("business_summary", values["business_summary"]),
        ("owner_staff_id", OWNER),
    ]
    filled = dict(slots[:enterprise_filled])
    return Enterprise(
        id=_case_ids(name),
        org_id=fixtures.ORG_ID,
        site_id=SITE,
        name=name,
        owner_staff_id=filled.get("owner_staff_id"),
        industry=filled.get("industry"),
        track=filled.get("track"),
        stage=filled.get("stage"),
        registered_location=filled.get("registered_location"),
        business_summary=filled.get("business_summary"),
        uscc=fixtures.FAKE_USCC,
        contact_phone=fixtures.FAKE_PHONE,
        created_at=NOW,
        updated_at=NOW,
    )


def _build_contact(ent: Enterprise, job_title: bool, decision_role: bool) -> Contact:
    return Contact(
        id=uuid.uuid5(uuid.NAMESPACE_DNS, "1861.contact." + ent.name),
        org_id=fixtures.ORG_ID,
        site_id=SITE,
        enterprise_id=ent.id,
        full_name="联系人",
        job_title="运营总监" if job_title else None,
        decision_role="决策者" if decision_role else None,
        phone="10000000000",
        is_primary=True,
        created_at=NOW,
        updated_at=NOW,
    )


def completeness_of(case: tuple[str, int, bool, bool]) -> float:
    _name, enterprise_filled, job_title, decision_role = case
    return (enterprise_filled + int(job_title) + int(decision_role)) / 8.0


def expected_below() -> list[str]:
    return [case[0] for case in CASES if completeness_of(case) < 0.8]


def build_bundle() -> CrmBundle:
    enterprises = [_build_case(*case) for case in CASES]
    contacts = {
        ent.id: _build_contact(ent, case[2], case[3])
        for ent, case in zip(enterprises, CASES, strict=True)
    }
    cards = [
        CapabilityCard(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, "1861.card." + ent.name),
            org_id=fixtures.ORG_ID,
            site_id=SITE,
            enterprise_id=ent.id,
            card_key="capacity",
            confirmed_at=NOW,
            created_at=NOW,
            updated_at=NOW,
        )
        for ent in enterprises
    ]
    return CrmBundle(enterprises=enterprises, contacts_by_enterprise=contacts, cards=cards)


def make_client(snapshot: CaliberSnapshot | None = None) -> TestClient:
    provider = StaticCaliberProvider(
        {snapshot.version: snapshot} if snapshot else build_default_versions(),
        snapshot.version if snapshot else "v1",
    )
    composer = StaticComposer(
        crm_reader=StubCrmReader({SITE: build_bundle()}),
        caliber=provider,
        cache=InMemoryCache(),
        staff_names={OWNER: "会员经理甲"},
        now=NOW,
    )
    return TestClient(create_app(composer=composer))


def get_data(client: TestClient, **params: object) -> dict[str, Any]:
    token = make_token(org_id=fixtures.ORG_ID, site_ids=[SITE])
    response = client.get(
        "/api/dash/data-quality",
        params={"site_id": str(SITE), **params},
        headers=auth_header(token),
    )
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()["data"]
    return data


def test_low_list_key_set_is_exactly_id_and_name() -> None:
    rows = get_data(make_client())["low_completeness"]
    assert rows, "fixture must contain at least one row below 80%"
    for row in rows:
        assert set(row.keys()) == {"id", "name"}


def test_low_list_has_two_fields_only() -> None:
    row = get_data(make_client())["low_completeness"][0]
    assert len(row) == 2
    assert sorted(row) == ["id", "name"]


def test_low_list_contains_no_sensitive_keys_or_values() -> None:
    client = make_client()
    body = client.get(
        "/api/dash/data-quality",
        params={"site_id": str(SITE)},
        headers=auth_header(make_token(org_id=fixtures.ORG_ID, site_ids=[SITE])),
    ).text
    low_section = body.split('"low_completeness"', 1)[1].split(
        '"low_completeness_threshold_pct"', 1
    )[0]
    for forbidden in FORBIDDEN_KEYS:
        assert f'"{forbidden}"' not in low_section
    for value in SENSITIVE_VALUES:
        assert value not in body


def test_low_list_count_equals_number_of_enterprises_below_threshold() -> None:
    data = get_data(make_client())
    expected = expected_below()
    assert len(expected) == 5
    assert data["low_completeness_total"] == len(expected)
    assert len(data["low_completeness"]) == len(expected)
    assert [row["name"] for row in data["low_completeness"]] == sorted(
        expected,
        key=lambda name: (completeness_of(next(c for c in CASES if c[0] == name)), _case_ids(name)),
    )


def test_low_list_is_sorted_ascending_by_completeness() -> None:
    rows = get_data(make_client())["low_completeness"]
    scores = [
        completeness_of(next(case for case in CASES if case[0] == row["name"])) for row in rows
    ]
    assert scores == sorted(scores)


def test_exact_80_percent_stays_out_and_below_enters() -> None:
    """On an eight-field caliber, 80% needs 6.4 cells, so the edge is shown on a
    five-field caliber: 4/5 = 0.8000 exactly stays out, 3/5 = 0.6000 enters."""
    five_fields = (
        "enterprise.industry",
        "enterprise.track",
        "enterprise.stage",
        "enterprise.registered_location",
        "enterprise.business_summary",
    )
    snapshot = CaliberSnapshot(
        version="v5",
        fields=five_fields,
        labels={},
        target_pct=95.0,
        low_pct=80.0,
        fresh_days=90,
    )
    exact = _build_case("临界八十", 4, False, False)
    below = _build_case("临界之下", 3, False, False)
    bundle = CrmBundle(enterprises=[exact, below], contacts_by_enterprise={}, cards=[])
    composer = StaticComposer(
        crm_reader=StubCrmReader({SITE: bundle}),
        caliber=StaticCaliberProvider({"v5": snapshot}, "v5"),
        cache=InMemoryCache(),
        now=NOW,
    )
    data = get_data(TestClient(create_app(composer=composer)))
    assert data["completeness"] == 0.7
    names = [row["name"] for row in data["low_completeness"]]
    assert "临界八十" not in names, "exactly 80.00% is not below the threshold"
    assert names == ["临界之下"]


def test_threshold_predicate_is_strict_at_eighty_percent() -> None:
    """80.00% stays out, 79.99% goes in."""
    from app.calc.completeness import is_below_threshold

    assert is_below_threshold(0.7999, 0.80) is True
    assert is_below_threshold(0.80, 0.80) is False
    assert is_below_threshold(0.8001, 0.80) is False

def test_limit_default_is_50_and_upper_bound_is_200() -> None:
    client = make_client()
    token = make_token(org_id=fixtures.ORG_ID, site_ids=[SITE])
    too_big = client.get(
        "/api/dash/data-quality",
        params={"site_id": str(SITE), "limit": 201},
        headers=auth_header(token),
    )
    assert too_big.status_code == 422
    ok = client.get(
        "/api/dash/data-quality",
        params={"site_id": str(SITE), "limit": 200},
        headers=auth_header(token),
    )
    assert ok.status_code == 200
    assert len(ok.json()["data"]["low_completeness"]) == 5
    limited = client.get(
        "/api/dash/data-quality",
        params={"site_id": str(SITE), "limit": 2},
        headers=auth_header(token),
    )
    assert len(limited.json()["data"]["low_completeness"]) == 2


def test_permission_scope_and_anonymous_are_rejected() -> None:
    client = make_client()
    no_scope = make_token(org_id=fixtures.ORG_ID, site_ids=[SITE], scope="other.read")
    denied = client.get(
        "/api/dash/data-quality", params={"site_id": str(SITE)}, headers=auth_header(no_scope)
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == 40301
    anonymous = client.get("/api/dash/data-quality", params={"site_id": str(SITE)})
    assert anonymous.status_code == 401
    assert anonymous.json()["code"] == 40101