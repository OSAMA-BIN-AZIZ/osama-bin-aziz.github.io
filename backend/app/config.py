from functools import lru_cache

from pydantic import AnyHttpUrl, EmailStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=True,
        extra='ignore',
    )

    app_name: str = Field(default='V2free Secure Backend', alias='APP_NAME')
    app_env: str = Field(default='development', alias='APP_ENV')
    app_host: str = Field(default='0.0.0.0', alias='APP_HOST')
    app_port: int = Field(default=8000, alias='APP_PORT')
    app_base_url: AnyHttpUrl = Field(default='http://localhost:8000', alias='APP_BASE_URL')
    cors_origins: str = Field(default='http://localhost:3000', alias='CORS_ORIGINS')

    database_url: str = Field(alias='DATABASE_URL')

    jwt_secret_key: str = Field(alias='JWT_SECRET_KEY', min_length=32)
    jwt_refresh_secret_key: str = Field(alias='JWT_REFRESH_SECRET_KEY', min_length=32)
    data_encryption_key: str = Field(alias='DATA_ENCRYPTION_KEY', min_length=32)

    access_token_expire_minutes: int = Field(default=15, alias='ACCESS_TOKEN_EXPIRE_MINUTES')
    refresh_token_expire_minutes: int = Field(default=60 * 24 * 30, alias='REFRESH_TOKEN_EXPIRE_MINUTES')
    cookie_secure: bool = Field(default=True, alias='COOKIE_SECURE')

    admin_bootstrap_email: EmailStr = Field(alias='ADMIN_BOOTSTRAP_EMAIL')
    admin_bootstrap_password: str = Field(alias='ADMIN_BOOTSTRAP_PASSWORD', min_length=12)

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(',') if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
