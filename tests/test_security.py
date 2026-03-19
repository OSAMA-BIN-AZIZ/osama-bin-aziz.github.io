import os
import sys
import types
import unittest
from pathlib import Path

os.environ.setdefault("APP_SECRET_KEY", "a" * 32)
os.environ.setdefault("SUBSCRIPTION_SIGNING_KEY", "b" * 32)
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://user:pass@127.0.0.1:5432/app")
os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")


class _HTTPException(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


fake_fastapi = types.ModuleType("fastapi")
fake_fastapi.HTTPException = _HTTPException
fake_fastapi.status = types.SimpleNamespace(HTTP_401_UNAUTHORIZED=401)
sys.modules.setdefault("fastapi", fake_fastapi)

from backend import security
from backend.config import ConfigError, get_settings


class SecurityTests(unittest.TestCase):
    def test_password_hash_and_verify(self) -> None:
        hashed, salt = security.hash_password("StrongPassword!123")
        self.assertTrue(security.verify_password("StrongPassword!123", hashed, salt))
        self.assertFalse(security.verify_password("WrongPassword!123", hashed, salt))

    def test_subscription_token_roundtrip(self) -> None:
        token = security.create_subscription_token(subscription_id=9, token_version=2, region="hk")
        payload = security.decode_subscription_token(token)
        self.assertEqual(payload["sid"], 9)
        self.assertEqual(payload["ver"], 2)
        self.assertEqual(payload["region"], "hk")

    def test_database_ssl_is_enforced(self) -> None:
        settings = get_settings()
        self.assertIn("sslmode=require", settings.database_url)


    def test_bootstrap_password_placeholder_is_rejected(self) -> None:
        original = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD")
        try:
            os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "ChangeMeNow!123456"
            get_settings.cache_clear()
            with self.assertRaises(ConfigError):
                get_settings()
        finally:
            if original is None:
                os.environ.pop("BOOTSTRAP_ADMIN_PASSWORD", None)
            else:
                os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = original
            get_settings.cache_clear()

    def test_subscription_model_allows_multiple_rows_per_user_version(self) -> None:
        models_source = Path("backend/models.py").read_text(encoding="utf-8")
        self.assertNotIn("uq_subscription_token_version_per_user", models_source)
        self.assertNotIn('UniqueConstraint("token_version", "user_id"', models_source)


if __name__ == "__main__":
    unittest.main()
