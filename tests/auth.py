"""Bearer tokens for the test client.

The production token is issued by the platform SSO; here the same HS256 secret from
the environment is used, so the permission dependency is exercised for real instead
of being stubbed out.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.config import get_settings

ALL_SCOPES = "dash.quality.read other.read"


def make_token(
    *,
    org_id: uuid.UUID,
    site_ids: list[uuid.UUID] | None = None,
    scope: str = ALL_SCOPES,
    expires_in: timedelta = timedelta(hours=1),
    subject: str = "tester",
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "org_id": str(org_id),
        "site_ids": [str(item) for item in (site_ids or [])],
        "scope": scope,
        "aud": settings.jwt_audience,
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": now + expires_in,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
