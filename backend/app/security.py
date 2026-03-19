from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from cryptography.fernet import Fernet
from fastapi import HTTPException, status

from .config import settings


def _build_fernet() -> Fernet:
    key = settings.fernet_secret
    if key == "REPLACE_WITH_FERNET_KEY":
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.jwt_secret.encode()).digest()).decode()
    return Fernet(key.encode())


fernet = _build_fernet()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 390000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    salt, digest = password_hash.split("$", 1)
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 390000)
    return secrets.compare_digest(candidate.hex(), digest)


def create_access_token(subject: str, role: str) -> tuple[str, int]:
    expires_in = settings.jwt_exp_minutes * 60
    payload = {
        "sub": subject,
        "role": role,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(seconds=expires_in),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return token, expires_in


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效或过期令牌") from exc


def encrypt_text(value: str) -> bytes:
    return fernet.encrypt(value.encode())


def decrypt_text(value: bytes) -> str:
    try:
        return fernet.decrypt(value).decode()
    except Exception as exc:  # noqa: BLE001 - surfaced as auth-like denial intentionally
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="订阅内容解密失败") from exc
