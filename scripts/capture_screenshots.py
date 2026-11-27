"""Capture delivery screenshots with Playwright (optional dev tool).

Usage:
    pip install playwright && playwright install chromium
    python scripts/capture_screenshots.py

Produces three PNGs under docs/screenshots/:
    01-swagger-ui.png         the OpenAPI document rendered by Swagger UI
    02-response-json.png     the endpoint envelope as returned by the API
    03-hand-calculation.png  the hand-calculation table printed by the AC1 test

The Swagger UI assets have to sit next to the script (vendor/swagger-ui-dist);
without them the script still writes the two other screenshots. This script is not
part of the verification pipeline, it only produces the delivery evidence images.
"""

from __future__ import annotations

import html
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"
VENDOR = ROOT / "vendor" / "swagger-ui-dist"

SWAGGER_HTML = """<!doctype html>
<html><head><meta charset="utf-8">
<link rel="stylesheet" href="__CSS__">
</head><body>
<div id="swagger-ui"></div>
<script src="__JS__"></script>
<script>
window.onload = function() {
  window.ui = SwaggerUIBundle({spec: __SPEC__, dom_id: "#swagger-ui", deepLinking: true});
};
</script>
</body></html>
"""

JSON_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><style>
body { background:#0f172a; color:#e2e8f0; margin:0; padding:24px;
 font-family: Consolas, Menlo, monospace; }
h1 { font-family: Segoe UI, sans-serif; font-size:18px; color:#7dd3fc; }
pre { white-space: pre-wrap; word-break: break-all; font-size:13px; margin:0; }
</style></head><body>
<h1>__TITLE__</h1>
<pre>__BODY__</pre>
</body></html>
"""


def _json_page(work: Path, name: str, title: str, body: str) -> Path:
    page = work / name
    page.write_text(
        JSON_HTML.replace("__TITLE__", title).replace("__BODY__", html.escape(body)),
        encoding="utf-8",
    )
    return page


def _swagger_page(work: Path) -> Path | None:
    """Render the real OpenAPI document with the vendored Swagger UI assets."""
    bundle = VENDOR / "swagger-ui-bundle.js"
    css = VENDOR / "swagger-ui.css"
    if not bundle.exists() or not css.exists():
        return None
    assets = work / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for item in VENDOR.iterdir():
        if item.is_file():
            shutil.copy2(item, assets / item.name)
    spec = json.loads((ROOT / "docs" / "checks" / "openapi.json").read_text(encoding="utf-8"))
    page = work / "swagger.html"
    page.write_text(
        SWAGGER_HTML.replace("__CSS__", "assets/swagger-ui.css")
        .replace("__JS__", "assets/swagger-ui-bundle.js")
        .replace("__SPEC__", json.dumps(spec, ensure_ascii=False)),
        encoding="utf-8",
    )
    return page


def _run_hand_calc() -> str:
    """Run the AC1 test with -s so the hand-calculation table is captured."""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-s", "-q", "tests/test_ac1_completeness.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    return proc.stdout


def _evidence_text() -> str:
    evidence = ROOT / "docs" / "evidence"
    for name in ("response-v1.json", "response-v2.json"):
        path = evidence / name
        if path.exists():
            return path.read_text(encoding="utf-8")
    return "{}"


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright is not installed; run: pip install playwright", file=sys.stderr)
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    work = ROOT / ".screenshot-work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    pages = [
        (
            _json_page(
                work,
                "response.html",
                "GET /api/dash/data-quality"
                "?site_id=11111111-1111-4111-8111-111111111111",
                _evidence_text(),
            ),
            "02-response-json.png",
        ),
        (
            _json_page(
                work,
                "handcalc.html",
                "pytest -s tests/test_ac1_completeness.py",
                _run_hand_calc(),
            ),
            "03-hand-calculation.png",
        ),
    ]
    swagger = _swagger_page(work)
    if swagger is not None:
        pages.insert(0, (swagger, "01-swagger-ui.png"))
    else:
        print("vendor/swagger-ui-dist missing, skipping the Swagger UI screenshot", file=sys.stderr)

    with sync_playwright() as play:
        browser = play.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        for source, name in pages:
            page.goto(source.resolve().as_uri())
            page.wait_for_timeout(1500)
            page.screenshot(path=str(OUT / name), full_page=True)
            print(f"wrote {OUT / name}")
        browser.close()
    shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())