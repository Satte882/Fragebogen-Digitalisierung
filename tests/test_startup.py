"""Missing production secrets must fail startup, not silently bypass login."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import build_app
from app.security import password_hash


def test_missing_secrets_fail_closed():
    app=build_app(Settings(admin_password_hash='',test_password_hash='',session_secret=''))
    with pytest.raises(RuntimeError, match='Credentials missing'):
        with TestClient(app):
            pass


def test_production_rejects_malformed_hash_and_disabled_live_model():
    valid = password_hash('test-only')
    with pytest.raises(RuntimeError, match='scrypt'):
        Settings('scrypt$fake$fake', valid, 'x' * 32, app_env='production').validate()
    with pytest.raises(RuntimeError, match='Live model is disabled'):
        Settings(valid, valid, 'x' * 32, model_provider='openrouter', app_env='production',
                 openrouter_api_key='placeholder', openrouter_model='placeholder', allow_live_model=False).validate()
