"""Flip the active caliber version for the demo site.

python scripts/set_caliber_version.py v2
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db import get_session_factory
from app.models.caliber import CaliberFieldVersion


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: set_caliber_version.py <version>")
        return 2
    target = argv[1]
    session = get_session_factory()()
    try:
        rows = session.execute(select(CaliberFieldVersion)).scalars().all()
        if not any(row.version == target for row in rows):
            print(f"unknown version {target}; known: {[row.version for row in rows]}")
            return 2
        for row in rows:
            row.is_active = row.version == target
        session.commit()
        print(f"active caliber version = {target}")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
