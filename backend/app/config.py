from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "V2free Secure API")
    app_env: str = os.getenv("APP_ENV", "development")
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    app_base_url: str = os.getenv("APP_BASE_URL", "http://localhost:8000")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/v2free",
    )
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me-please")
    jwt_exp_minutes: int = int(os.getenv("JWT_EXP_MINUTES", "60"))
    fernet_secret: str = os.getenv(
        "FERNET_SECRET",
        "REPLACE_WITH_FERNET_KEY",
    )
    initial_admin_email: str = os.getenv("INITIAL_ADMIN_EMAIL", "admin@example.com")
    initial_admin_password: str = os.getenv(
        "INITIAL_ADMIN_PASSWORD",
        "ChangeThisAdminPasswordImmediately!",
    )
    cors_origins: tuple[str, ...] = tuple(
        item.strip()
        for item in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
        if item.strip()
    )


settings = Settings()
