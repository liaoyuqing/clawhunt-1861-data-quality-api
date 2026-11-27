"""Smoke-test the endpoint against the real PostgreSQL mirror and capture the JSON.

    DQ_DATABASE_URL=... python scripts/smoke_api.py --version v1
    DQ_DATABASE_URL=... python scripts/smoke_api.py --version v2

The optional --version flag flips the active caliber version in the database first,
so the two versions can be captured one after the other for the AC2 evidence.

Writes docs/evidence/response-v{version}.json and docs/evidence/response-v{version}-staff.json
(the raw envelopes a reviewer can diff) plus docs/checks/smoke.txt.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402
from tests import fixtures  # noqa: E402
from tests.auth import auth_header, make_token  # noqa: E402


def _activate(version: str) -> str:
    """Make the given caliber version the active one and return the previous one."""
    from sqlalchemy import select

    from app.db import get_session_factory
    from app.models.caliber import CaliberFieldVersion

    session = get_session_factory()()
    try:
        rows = session.execute(select(CaliberFieldVersion)).scalars().all()
        if not any(row.version == version for row in rows):
            raise SystemExit(f"caliber version {version} is not seeded")
        current = next((row.version for row in rows if row.is_active), "")
        for row in rows:
            row.is_active = row.version == version
        session.commit()
        return current
    finally:
        session.close()


def main() -> int:
    # The httpx access log would otherwise drown the captured envelope.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    args = sys.argv[1:]
    if args:
        if args[0] not in ("--version", "-V") or len(args) != 2:
            print("usage: smoke_api.py [--version v1|v2]", file=sys.stderr)
            return 2
        version = args[1]

    evidence = ROOT / "docs" / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    checks = ROOT / "docs" / "checks"
    checks.mkdir(parents=True, exist_ok=True)

    previous = _activate(version)

    app = create_app()
    token = make_token(org_id=fixtures.ORG_ID, site_ids=[fixtures.SITE_ID])
    headers = auth_header(token)
    lines: list[str] = [f"CALIBER_VERSION={version}"]

    with TestClient(app) as client:
        for label, params in (
            (version, {"site_id": str(fixtures.SITE_ID)}),
            (
                f"{version}-staff",
                {"site_id": str(fixtures.SITE_ID), "staff_id": str(fixtures.MANAGER_A)},
            ),
        ):
            response = client.get("/api/dash/data-quality", params=params, headers=headers)
            body = response.json()
            (evidence / f"response-{label}.json").write_text(
                json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            lines.append(f"--- {label} HTTP {response.status_code} ---")
            lines.append(json.dumps(body, ensure_ascii=False, indent=2))
            lines.append("")

    report = "\n".join(lines)
    (checks / f"smoke-{version}.txt").write_text(report, encoding="utf-8")
    (checks / "smoke.txt").write_text(report, encoding="utf-8")
    print(report)
    # Leave the database exactly as it was found.
    if previous:
        _activate(previous)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())