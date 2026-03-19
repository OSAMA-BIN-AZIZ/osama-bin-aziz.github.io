import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from cryptography.fernet import Fernet
from config import get_settings

settings = get_settings()


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    derived_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 390000)
    return f"{base64.b64encode(salt).decode()}${base64.b64encode(derived_key).decode()}"


def verify_password(password: str, password_hash: str) -> bool:
    salt_b64, hash_b64 = password_hash.split("$", 1)
    salt = base64.b64decode(salt_b64.encode())
    expected_hash = base64.b64decode(hash_b64.encode())
    supplied_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 390000)
    return hmac.compare_digest(expected_hash, supplied_hash)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc

    subject = payload.get("sub")
    if not subject:
        raise ValueError("Token missing subject")
    return str(subject)


def get_fernet() -> Fernet:
    return Fernet(settings.content_encryption_key.encode("utf-8"))


def encrypt_content(plaintext: str) -> bytes:
    return get_fernet().encrypt(plaintext.encode("utf-8"))


def decrypt_content(ciphertext: bytes) -> str:
    return get_fernet().decrypt(ciphertext).decode("utf-8")
