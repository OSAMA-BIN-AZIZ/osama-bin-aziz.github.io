from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status

from .config import get_settings

settings = get_settings()



def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    actual_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), actual_salt.encode("utf-8"), 310_000)
    return base64.urlsafe_b64encode(digest).decode("utf-8"), actual_salt



def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    calculated_hash, _ = hash_password(password, salt=salt)
    return hmac.compare_digest(calculated_hash, stored_hash)



def _encode_payload(payload: dict[str, object], key: str) -> str:
    content = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")).decode("utf-8")
    signature = hmac.new(key.encode("utf-8"), content.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{content}.{signature}"



def _decode_payload(token: str, key: str) -> dict[str, object]:
    try:
        content, signature = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format") from exc

    expected = hmac.new(key.encode("utf-8"), content.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token signature")

    payload = json.loads(base64.urlsafe_b64decode(content.encode("utf-8")).decode("utf-8"))
    expires_at = datetime.fromisoformat(str(payload["exp"]))
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    return payload



def create_access_token(user_id: int, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": (datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_ttl_minutes)).isoformat(),
        "type": "access",
    }
    return _encode_payload(payload, settings.secret_key)



def decode_access_token(token: str) -> dict[str, object]:
    payload = _decode_payload(token, settings.secret_key)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong token type")
    return payload



def create_subscription_token(subscription_id: int, token_version: int, region: str) -> str:
    payload = {
        "sid": subscription_id,
        "ver": token_version,
        "region": region,
        "exp": (datetime.now(timezone.utc) + timedelta(minutes=settings.subscription_token_ttl_minutes)).isoformat(),
        "type": "sub-link",
        "nonce": secrets.token_hex(8),
    }
    return _encode_payload(payload, settings.subscription_signing_key)



def decode_subscription_token(token: str) -> dict[str, object]:
    payload = _decode_payload(token, settings.subscription_signing_key)
    if payload.get("type") != "sub-link":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong subscription token type")
    return payload
