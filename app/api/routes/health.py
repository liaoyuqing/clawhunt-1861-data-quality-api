"""Liveness and readiness probes."""

from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.calc.registry import registered_names

router = APIRouter(tags=["ops"])


@router.get("/healthz", summary="Liveness probe")
def healthz() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/readyz", summary="Readiness probe with registered calc names")
def readyz() -> dict[str, object]:
    return {"status": "ok", "calc_refs": registered_names()}
