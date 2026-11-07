"""Runtime settings; never persist secrets in this repository."""
from __future__ import annotations

from dataclasses import dataclass
import os
from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    admin_password_hash: str
    test_password_hash: str
    session_secret: str
    model_provider: str = "mock"
    openrouter_api_key: str = ""
    openrouter_model: str = ""
    app_env: str = "development"
    max_images_per_session: int = 20
    max_upload_mb: int = 10
    session_ttl_minutes: int = 60

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            admin_password_hash=os.getenv("ADMIN_PASSWORD_HASH", ""),
            test_password_hash=os.getenv("TEST_PASSWORD_HASH", ""),
            session_secret=os.getenv("SESSION_SECRET", ""),
            model_provider=os.getenv("MODEL_PROVIDER", "mock"),
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
            openrouter_model=os.getenv("OPENROUTER_MODEL", ""),
            app_env=os.getenv("APP_ENV", "development"),
            max_images_per_session=int(os.getenv("MAX_IMAGES_PER_SESSION", "20")),
            max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", "10")),
            session_ttl_minutes=int(os.getenv("SESSION_TTL_MINUTES", "60")),
        )

    def validate(self) -> None:
        if not (self.admin_password_hash and self.test_password_hash and len(self.session_secret) >= 32):
            raise RuntimeError("Credentials missing. Run `python scripts/bootstrap_local.py` or configure Render secrets.")
        if not all(x.startswith("scrypt$") for x in (self.admin_password_hash, self.test_password_hash)):
            raise RuntimeError("Password hashes must be in scrypt format (bootstrap_local.py).")
        if self.model_provider not in ("mock", "openrouter"):
            raise RuntimeError("MODEL_PROVIDER must be mock or openrouter.")
        if self.model_provider == "openrouter" and not (self.openrouter_api_key and self.openrouter_model):
            raise RuntimeError("OPENROUTER_API_KEY and OPENROUTER_MODEL are required for the live model.")
        if self.max_images_per_session < 1 or self.max_upload_mb < 1 or self.session_ttl_minutes < 1:
            raise RuntimeError("Upload and session limits must be positive.")
