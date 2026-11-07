"""Missing production secrets must fail startup, not silently bypass login."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import build_app


def test_missing_secrets_fail_closed():
    app=build_app(Settings(admin_password_hash='',test_password_hash='',session_secret=''))
    with pytest.raises(RuntimeError, match='Credentials missing'):
        with TestClient(app):
            pass
