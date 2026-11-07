from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import build_app
from app.security import password_hash


@pytest.fixture
def application():
    settings = Settings(
        admin_password_hash=password_hash('admin-pass-123'),
        test_password_hash=password_hash('test-pass-123'),
        session_secret='test-only-secret-' + 'a' * 48,
        model_provider='mock',
        app_env='development',
        max_images_per_session=20,
        max_upload_mb=10,
        session_ttl_minutes=60,
    )
    return build_app(settings)


@pytest.fixture
def client(application):
    with TestClient(application) as c:
        yield c


def login(client, role='test'):
    pwd = 'admin-pass-123' if role == 'admin' else 'test-pass-123'
    r = client.post('/api/login', json={'username': role, 'password': pwd})
    assert r.status_code == 200, r.text
    return {'x-csrf-token': r.json()['csrf']}
