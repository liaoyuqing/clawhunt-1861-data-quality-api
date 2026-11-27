"""Integration tests against a real PostgreSQL 16 instance.

They are skipped automatically when DQ_TEST_DATABASE_URL is not set, so the unit
suite stays runnable without a database. The CI command sets it to the private
cluster started by scripts/start_pg.ps1.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC

import pytest
from sqlalchemy import select, text

from app.models.caliber import CaliberFieldVersion
from tests import fixtures

DB_URL = os.environ.get("DQ_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(not DB_URL, reason="DQ_TEST_DATABASE_URL not set")


def test_schema_has_every_business_table(db_session: object) -> None:
    session = db_session
    rows = (
        session.execute(  # type: ignore[attr-defined]
            text("select tablename from pg_tables where schemaname='public' order by tablename")
        )
        .scalars()
        .all()
    )
    assert "crm_enterprises" in rows
    assert "caliber_field_versions" in rows
    assert "alembic_version" in rows


def test_seeded_enterprises_are_fictional_and_complete(db_session: object) -> None:
    from app.models.crm import Enterprise

    session = db_session
    rows = (
        session.execute(  # type: ignore[attr-defined]
            select(Enterprise).where(Enterprise.site_id == fixtures.SITE_ID)
        )
        .scalars()
        .all()
    )
    assert len(rows) == 3
    assert {row.name for row in rows} == {"云栖生物", "星澜科技", "恒泰智造"}


def test_caliber_versions_are_stored_per_site(db_session: object) -> None:
    session = db_session
    rows = (
        session.execute(  # type: ignore[attr-defined]
            select(CaliberFieldVersion).where(CaliberFieldVersion.site_id == fixtures.SITE_ID)
        )
        .scalars()
        .all()
    )
    by_version = {row.version: row for row in rows}
    assert set(by_version) == {"v1", "v2"}
    assert len(by_version["v1"].fields) == 8
    assert len(by_version["v2"].fields) == 7
    assert by_version["v2"].is_active is True
    assert by_version["v1"].is_active is False


def test_soft_delete_keeps_rows_out_of_the_query(db_session: object) -> None:
    from datetime import datetime

    from app.models.crm import Enterprise
    from app.repositories.crm_repo import SqlCrmReader

    session = db_session
    ghost = Enterprise(
        id=uuid.uuid5(uuid.NAMESPACE_DNS, "1861.ghost"),
        org_id=fixtures.ORG_ID,
        site_id=fixtures.SITE_ID,
        name="已删除企业",
        deleted_at=datetime.now(UTC),
        created_at=fixtures.NOW,
        updated_at=fixtures.NOW,
    )
    session.add(ghost)  # type: ignore[attr-defined]
    session.commit()  # type: ignore[attr-defined]
    bundle = SqlCrmReader(session).load(fixtures.SITE_ID, None)  # type: ignore[arg-type]
    assert "已删除企业" not in [row.name for row in bundle.enterprises]
    session.delete(ghost)  # type: ignore[attr-defined]
    session.commit()  # type: ignore[attr-defined]
