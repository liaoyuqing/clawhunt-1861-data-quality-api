"""Export the OpenAPI document of the dashboard API.

    python scripts/export_openapi.py

Writes docs/openapi.yaml (human readable fragment) and docs/checks/openapi.json
(the machine readable copy used by the verification script).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import create_app  # noqa: E402


def main() -> int:
    app = create_app()
    schema = app.openapi()
    docs = ROOT / "docs"
    checks = docs / "checks"
    checks.mkdir(parents=True, exist_ok=True)

    yaml_path = docs / "openapi.yaml"
    json_path = checks / "openapi.json"
    json_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    yaml_path.write_text(_to_yaml(schema), encoding="utf-8")

    paths = sorted(schema["paths"])
    print(f"OPENAPI_VERSION={schema['openapi']}")
    print(f"PATHS={len(paths)}")
    for path in paths:
        print(f"  {path} -> {sorted(schema['paths'][path])}")
    print(f"OPENAPI_YAML_BYTES={yaml_path.stat().st_size}")
    print(f"OPENAPI_JSON_BYTES={json_path.stat().st_size}")
    return 0


def _to_yaml(schema: dict) -> str:
    import yaml

    return yaml.safe_dump(schema, allow_unicode=True, sort_keys=False, width=100)


if __name__ == "__main__":
    raise SystemExit(main())