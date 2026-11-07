"""Runtime settings; never persist secrets in this repository."""
from __future__ import annotations

from dataclasses import dataclass
import os
from dotenv import load_dotenv

from .security import valid_password_hash


@dataclass(frozen=True)
class Settings:
    admin_password_hash: str
    test_password_hash: str
    session_secret: str
    model_provider: str = "mock"
    openrouter_api_key: str = ""
    openrouter_model: str = ""
    app_env: str = "development"
    max_images_per_session: int = 40
    max_upload_mb: int = 10
    session_ttl_minutes: int = 120
    batch_parallelism: int = 3
    provider_retries: int = 2
    live_calls_per_session: int = 100
    live_calls_global: int = 250
    image_max_edge: int = 2200
    image_jpeg_quality: int = 90
    max_sessions: int = 4
    max_workspace_mb: int = 48
    max_batch_upload_mb: int = 120
    allow_live_model: bool = True

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
            max_images_per_session=int(os.getenv("MAX_IMAGES_PER_SESSION", "40")),
            max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", "10")),
            session_ttl_minutes=int(os.getenv("SESSION_TTL_MINUTES", "120")),
            batch_parallelism=int(os.getenv("BATCH_PARALLELISM", "3")),
            provider_retries=int(os.getenv("PROVIDER_RETRIES", "2")),
            live_calls_per_session=int(os.getenv("LIVE_CALLS_PER_SESSION", "100")),
            live_calls_global=int(os.getenv("LIVE_CALLS_GLOBAL", "250")),
            image_max_edge=int(os.getenv("IMAGE_MAX_EDGE", "2200")),
            image_jpeg_quality=int(os.getenv("IMAGE_JPEG_QUALITY", "90")),
            max_sessions=int(os.getenv("MAX_SESSIONS", "4")),
            max_workspace_mb=int(os.getenv("MAX_WORKSPACE_MB", "48")),
            max_batch_upload_mb=int(os.getenv("MAX_BATCH_UPLOAD_MB", "120")),
            allow_live_model=os.getenv("ALLOW_LIVE_MODEL", "false" if os.getenv("APP_ENV") == "production" else "true").lower() == "true",
        )

    def validate(self) -> None:
        if not (self.admin_password_hash and self.test_password_hash and len(self.session_secret) >= 32):
            raise RuntimeError("Credentials missing. Run `python scripts/bootstrap_local.py` or configure Render secrets.")
        if not all(valid_password_hash(x) for x in (self.admin_password_hash, self.test_password_hash)):
            raise RuntimeError("Password hashes must be in scrypt format (bootstrap_local.py).")
        if self.app_env not in ("development", "production"):
            raise RuntimeError("APP_ENV must be development or production.")
        if self.model_provider == "openrouter" and not self.allow_live_model:
            raise RuntimeError("Live model is disabled by ALLOW_LIVE_MODEL.")
        if not (1 <= self.max_sessions <= 20 and self.max_workspace_mb > 0 and self.max_batch_upload_mb > 0):
            raise RuntimeError("Invalid workspace or upload limits.")
        if self.model_provider not in ("mock", "openrouter"):
            raise RuntimeError("MODEL_PROVIDER must be mock or openrouter.")
        if self.model_provider == "openrouter" and not (self.openrouter_api_key and self.openrouter_model):
            raise RuntimeError("OPENROUTER_API_KEY and OPENROUTER_MODEL are required for the live model.")
        if self.max_images_per_session < 1 or self.max_upload_mb < 1 or self.session_ttl_minutes < 1:
            raise RuntimeError("Upload and session limits must be positive.")
        if not (1 <= self.batch_parallelism <= 8 and 0 <= self.provider_retries <= 4
                and self.live_calls_per_session > 0 and self.live_calls_global > 0
                and 800 <= self.image_max_edge <= 4000 and 70 <= self.image_jpeg_quality <= 95):
            raise RuntimeError("Invalid processing, budget or image configuration.")
