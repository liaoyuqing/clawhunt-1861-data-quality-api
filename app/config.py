"""Runtime settings.

Every configuration value comes from the environment; nothing is hard-coded and no
secret is ever stored in the repository. Defaults are safe for local runs.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DQ_", env_file=None, extra="ignore")

    app_name: str = "member-space-data-quality-api"
    api_prefix: str = "/api"

    # PostgreSQL 16. Read-only CRM schema and the metric-caliber (kou-jing) schema.
    database_url: str = "postgresql+psycopg://postgres:postgres@127.0.0.1:55432/dq1861"

    # Production cache is Redis; tests inject fakeredis through the same client.
    redis_url: str = "redis://127.0.0.1:6379/0"
    cache_ttl_seconds: int = 60

    # Dashboard thresholds are owned by the metric-caliber library. The constants
    # below are only used when a caliber row does not carry an explicit override.
    default_target_pct: float = 95.0
    default_low_pct: float = 80.0
    default_fresh_days: int = 90

    # Auth: HS256 JWT issued by the platform SSO; only the public key/secret comes
    # from the environment, never from code.
    jwt_secret: str = "insecure-local-development-secret"
    jwt_algorithm: str = "HS256"
    jwt_audience: str = "member-space"
    jwt_issuer: str = "member-space-sso"

    # Permission scope required by the dashboard endpoints.
    required_scope: str = "dash.quality.read"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
