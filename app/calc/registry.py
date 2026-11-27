"""White-listed calculation registry.

The caliber library stores a calc_ref string per version. Only names registered
here may run, which keeps the caliber table from turning into a code-injection
surface.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

CalcFn = Callable[..., Any]

CALC_REGISTRY: dict[str, CalcFn] = {}


class UnknownCalcRef(LookupError):
    """Raised when a caliber version references a function that is not registered."""


def register(name: str) -> Callable[[CalcFn], CalcFn]:
    def decorator(func: CalcFn) -> CalcFn:
        CALC_REGISTRY[name] = func
        return func

    return decorator


def resolve_calc(name: str) -> CalcFn:
    try:
        return CALC_REGISTRY[name]
    except KeyError:
        raise UnknownCalcRef(name) from None


def registered_names() -> list[str]:
    return sorted(CALC_REGISTRY)
