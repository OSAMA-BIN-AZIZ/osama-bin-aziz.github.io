from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "V2free Secure Platform API"
    environment: str = Field(default="production")
    debug: bool = False
    api_prefix: str = "/api/v1"
    database_url: str = Field(
        default="postgresql+psycopg://v2free_app:change-me@db.example.com:5432/v2free"
    )
    jwt_secret_key: str = Field(default="change-me-to-a-32-char-secret")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    trusted_hosts: str = "localhost,127.0.0.1"
    cors_origins: str = "https://x.aziz-x.com"
    enforce_https_redirect: bool = True
    content_encryption_key: str = Field(
        default="QkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkI="
    )
    admin_bootstrap_email: str = "admin@example.com"
    login_rate_limit: int = 10
    login_rate_window_seconds: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def trusted_hosts_list(self) -> list[str]:
        return [host.strip() for host in self.trusted_hosts.split(",") if host.strip()]

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
