"""One-shot verification runner used by the delivery checklist.

    python scripts/verify_all.py

Runs, in order, and prints the exit code of every step:
  1. dependency install (pip install -r requirements-dev.txt)
  2. unit + integration tests (pytest)
  3. static type check (mypy --strict)
  4. lint (ruff check)
  5. package build (python -m build)
  6. OpenAPI export

Step 1 is skipped when --skip-install is passed.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(label: str, command: list[str], env: dict[str, str]) -> int:
    print(f"\n=== {label} ===", flush=True)
    print("$ " + " ".join(command), flush=True)
    result = subprocess.run(command, cwd=ROOT, env=env, check=False)
    print(f"=== {label} EXIT={result.returncode} ===", flush=True)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()

    env = dict(os.environ)
    python = sys.executable
    failures: list[str] = []

    if not args.skip_install:
        code = run(
            "dependency install",
            [python, "-m", "pip", "install", "-r", "requirements-dev.txt"],
            env,
        )
        if code != 0:
            failures.append("dependency install")

    code = run("pytest", [python, "-m", "pytest", "-v", "--no-header"], env)
    if code != 0:
        failures.append("pytest")

    code = run("mypy", [python, "-m", "mypy"], env)
    if code != 0:
        failures.append("mypy")

    code = run("ruff", [python, "-m", "ruff", "check", "."], env)
    if code != 0:
        failures.append("ruff")

    if not args.skip_build:
        code = run("build", [python, "-m", "build", "--wheel", "--sdist"], env)
        if code != 0:
            failures.append("build")

    code = run("openapi export", [python, "scripts/export_openapi.py"], env)
    if code != 0:
        failures.append("openapi export")

    print("\n=== SUMMARY ===")
    if failures:
        print("FAILED STEPS: " + ", ".join(failures))
        return 1
    print("ALL STEPS EXIT=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())