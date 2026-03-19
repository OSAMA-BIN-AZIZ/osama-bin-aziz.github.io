from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.fernet import Fernet
from jose import jwt
from pwdlib import PasswordHash

from .config import get_settings

settings = get_settings()
password_hasher = PasswordHash.recommended()
content_cipher = Fernet(settings.data_encryption_key.encode())


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hasher.verify(password, hashed_password)


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    return _create_token(subject, settings.jwt_secret_key, settings.access_token_expire_minutes, 'access', extra_claims)


def create_refresh_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    return _create_token(subject, settings.jwt_refresh_secret_key, settings.refresh_token_expire_minutes, 'refresh', extra_claims)


def _create_token(subject: str, secret: str, expires_in_minutes: int, token_type: str, extra_claims: dict[str, Any] | None) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        'sub': subject,
        'type': token_type,
        'iat': int(now.timestamp()),
        'exp': int((now + timedelta(minutes=expires_in_minutes)).timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, secret, algorithm='HS256')


def encrypt_text(plaintext: str) -> str:
    return content_cipher.encrypt(plaintext.encode()).decode()


def decrypt_text(ciphertext: str) -> str:
    return content_cipher.decrypt(ciphertext.encode()).decode()
