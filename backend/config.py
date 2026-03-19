from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse


class ConfigError(RuntimeError):
    """Raised when environment configuration is unsafe or incomplete."""


@dataclass(frozen=True)
class Settings:
    app_name: str
    environment: str
    secret_key: str
    subscription_signing_key: str
    database_url: str
    read_database_url: str | None
    cors_origins: tuple[str, ...]
    admin_email: str
    access_token_ttl_minutes: int
    subscription_token_ttl_minutes: int
    db_pool_size: int
    db_max_overflow: int
    require_db_ssl: bool

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"



def _get_required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value



def _normalize_origins(raw: str) -> tuple[str, ...]:
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    return tuple(origins or ["http://localhost:8000"])



def _ensure_postgres_ssl(url: str, require_ssl: bool) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"postgresql", "postgresql+psycopg", "postgresql+psycopg2"}:
        raise ConfigError("DATABASE_URL must use a PostgreSQL driver for remote deployment")

    if not require_ssl:
        return url

    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if query.get("sslmode") not in {"require", "verify-ca", "verify-full"}:
        query["sslmode"] = "require"
    return urlunparse(parsed._replace(query=urlencode(query)))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings(
        app_name=os.getenv("APP_NAME", "V2free Secure Platform"),
        environment=os.getenv("APP_ENV", "production"),
        secret_key=_get_required("APP_SECRET_KEY"),
        subscription_signing_key=_get_required("SUBSCRIPTION_SIGNING_KEY"),
        database_url=_ensure_postgres_ssl(
            _get_required("DATABASE_URL"),
            os.getenv("REQUIRE_DB_SSL", "true").lower() == "true",
        ),
        read_database_url=os.getenv("READ_DATABASE_URL", "").strip() or None,
        cors_origins=_normalize_origins(os.getenv("CORS_ORIGINS", "http://localhost:8000")),
        admin_email=_get_required("ADMIN_EMAIL"),
        access_token_ttl_minutes=int(os.getenv("ACCESS_TOKEN_TTL_MINUTES", "30")),
        subscription_token_ttl_minutes=int(os.getenv("SUBSCRIPTION_TOKEN_TTL_MINUTES", "10")),
        db_pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
        db_max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
        require_db_ssl=os.getenv("REQUIRE_DB_SSL", "true").lower() == "true",
    )

    if len(settings.secret_key) < 32:
        raise ConfigError("APP_SECRET_KEY must be at least 32 characters")
    if len(settings.subscription_signing_key) < 32:
        raise ConfigError("SUBSCRIPTION_SIGNING_KEY must be at least 32 characters")

    return settings
