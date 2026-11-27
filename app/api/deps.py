"""Shared FastAPI dependencies: database session, caller identity, permissions."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass

import jwt
from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.errors import ForbiddenError, UnauthorizedError


@dataclass(frozen=True, slots=True)
class Caller:
    subject: str
    org_id: uuid.UUID
    site_ids: tuple[uuid.UUID, ...]
    scopes: frozenset[str]


def get_session() -> Iterator[Session]:
    yield from get_db()


def _decode(token: str) -> dict[str, object]:
    settings = get_settings()
    try:
        payload: dict[str, object] = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("TOKEN_EXPIRED") from exc
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("TOKEN_INVALID") from exc
    return payload


def get_caller(authorization: str | None = Header(default=None)) -> Caller:
    """Decode the platform SSO token.

    Scopes are carried in the token, so the dashboard never queries an auth
    service on the request path.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("TOKEN_MISSING")
    payload = _decode(authorization.split(" ", 1)[1].strip())
    try:
        org_id = uuid.UUID(str(payload["org_id"]))
        raw_sites = payload.get("site_ids") or []
        if not isinstance(raw_sites, list):
            raise ValueError("site_ids must be a list")
        site_ids = tuple(uuid.UUID(str(item)) for item in raw_sites)
    except (KeyError, ValueError) as exc:
        raise UnauthorizedError("TOKEN_INVALID") from exc
    raw_scope = payload.get("scope")
    scope_text = raw_scope if isinstance(raw_scope, str) else ""
    scopes = frozenset(item for item in scope_text.split() if item)
    return Caller(
        subject=str(payload.get("sub", "")), org_id=org_id, site_ids=site_ids, scopes=scopes
    )


def require_scope(scope: str) -> Callable[[Caller], Caller]:
    def dependency(caller: Caller = Depends(get_caller)) -> Caller:
        if scope not in caller.scopes:
            raise ForbiddenError(scope)
        return caller

    return dependency


def assert_site_allowed(caller: Caller, site_id: uuid.UUID) -> None:
    """Token-scoped site allow-list, an additional guard next to the SQL filter."""
    if caller.site_ids and site_id not in caller.site_ids:
        raise ForbiddenError("site not in token scope")
