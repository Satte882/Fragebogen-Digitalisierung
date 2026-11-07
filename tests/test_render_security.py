from dataclasses import replace

from fastapi.testclient import TestClient

from app.main import build_app
from app.security import WorkspaceStore
from .conftest import login


def test_production_https_and_active_session_cap(application):
    app = build_app(replace(application.state.settings, app_env="production", max_sessions=2,
                            allow_live_model=False, openrouter_api_key="placeholder-never-returned"))
    with TestClient(app, base_url="https://pilot.test") as admin, TestClient(app, base_url="https://pilot.test") as invited:
        credentials = {"username": "admin", "password": "admin-pass-123"}
        response = admin.post("/api/login", json=credentials)
        assert response.status_code == 200
        cookie = response.headers["set-cookie"].lower()
        assert all(flag in cookie for flag in ("secure", "httponly", "samesite=lax"))
        headers = {"x-csrf-token": response.json()["csrf"]}
        invite_headers = login(invited)
        assert invited.get("/api/admin/config").status_code == 403
        assert admin.get("http://pilot.test/api/me").status_code == 401
        assert "placeholder-never-returned" not in admin.get("/api/admin/config").text
        assert admin.post("/api/admin/config", headers=headers,
                          json={"provider":"openrouter", "model":"model"}).status_code == 403
        with TestClient(app, base_url="https://pilot.test") as third:
            assert third.post("/api/login", json=credentials).status_code == 429
            assert invited.post("/api/logout", headers=invite_headers).status_code == 200
            assert third.post("/api/login", json=credentials).status_code == 200


def test_json_size_limit_and_validation_redaction(client):
    password = "test-do-not-echo-" * 30
    error = client.post("/api/login", json={"username": "test", "password": password})
    assert error.status_code == 422 and "test-do-not-echo" not in error.text
    assert client.post("/api/login", content=b"x" * 66000).status_code == 413
    assert client.get("/health").status_code == 200


def test_ip_and_global_login_limits():
    now = [100]
    store = WorkspaceStore(120, now=lambda: now[0])
    for _ in range(8):
        assert not store.is_rate_limited("ip")
        store.record_login_attempt("ip")
    assert store.is_rate_limited("ip")
    for index in range(32):
        assert not store.is_rate_limited(str(index))
    assert store.is_rate_limited("another")
    now[0] += 61
    assert not store.is_rate_limited("ip")
