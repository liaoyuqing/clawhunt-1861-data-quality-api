"""Shared pytest fixtures: an app wired to the fictional dataset and fakeredis."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import fakeredis
import pytest
from fastapi.testclient import TestClient

from app.cache.client import RedisCache
from app.di import StaticComposer
from app.main import create_app
from app.repositories.caliber_repo import StaticCaliberProvider, build_default_versions
from app.repositories.crm_repo import StubCrmReader
from tests import fixtures
from tests.auth import auth_header, make_token


@dataclass
class Harness:
    client: TestClient
    cache: Any
    caliber: StaticCaliberProvider
    composer: StaticComposer
    headers: dict[str, str]

    @property
    def site(self) -> str:
        return str(fixtures.SITE_ID)

    def get(self, **params: object) -> Any:
        query = {"site_id": self.site, **params}
        return self.client.get("/api/dash/data-quality", params=query, headers=self.headers)


def build_harness(now: Any = fixtures.NOW) -> Harness:
    versions = build_default_versions()
    provider = StaticCaliberProvider(versions, "v1")
    server = fakeredis.FakeServer()
    cache = RedisCache.__new__(RedisCache)
    cache._client = fakeredis.FakeStrictRedis(server=server, decode_responses=True)
    composer = StaticComposer(
        crm_reader=StubCrmReader({fixtures.SITE_ID: fixtures.build_bundle()}),
        caliber=provider,
        cache=cache,
        staff_names={fixtures.MANAGER_A: "会员经理甲", fixtures.MANAGER_B: "会员经理乙"},
        ttl_seconds=60,
        now=now,
    )
    app = create_app(composer=composer)
    token = make_token(org_id=fixtures.ORG_ID, site_ids=[fixtures.SITE_ID])
    return Harness(
        client=TestClient(app),
        cache=cache,
        caliber=provider,
        composer=composer,
        headers=auth_header(token),
    )


@pytest.fixture(scope="session")
def db_session() -> Iterator[Any]:
    """A real PostgreSQL 16 session, or a skip when no test database is configured.

    The private cluster is started by scripts/start_pg.ps1 and seeded by
    scripts/seed_demo.py; DQ_TEST_DATABASE_URL points at it.
    """
    import os

    url = os.environ.get("DQ_TEST_DATABASE_URL")
    if not url:
        pytest.skip("DQ_TEST_DATABASE_URL not set")

    from sqlalchemy import text

    from app.config import get_settings
    from app.db import get_engine, get_session_factory, reset_engine
    from app.repositories.caliber_repo import CaliberDbProvider

    os.environ["DQ_DATABASE_URL"] = url
    get_settings.cache_clear()
    reset_engine()
    with get_engine().begin() as connection:
        connection.execute(text("select 1"))
    session = get_session_factory()()
    # The seeded database ships both caliber versions; the active pointer is
    # flipped by scripts/set_caliber_version.py and by the smoke runs, so the
    # fixture sets it deterministically instead of relying on leftover state.
    original = _activate_version(session, "v2")
    snapshot = CaliberDbProvider(session).active(str(fixtures.SITE_ID))
    assert snapshot.version == "v2"
    try:
        yield session
    finally:
        _activate_version(session, original)
        session.close()
        reset_engine()


def _activate_version(session: Any, version: str) -> str:
    """Make one caliber version active and return the one that was active before."""
    from sqlalchemy import select

    from app.models.caliber import CaliberFieldVersion

    rows = session.execute(select(CaliberFieldVersion)).scalars().all()
    current = next((row.version for row in rows if row.is_active), "")
    for row in rows:
        row.is_active = row.version == version
    session.commit()
    return current


@pytest.fixture()
def harness() -> Iterator[Harness]:
    built = build_harness()
    yield built
    built.client.close()
