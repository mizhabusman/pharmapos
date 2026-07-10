"""Tests for the authentication layer and route protection."""

import app.core.security as security
from app.core.config import INSECURE_SECRET_DEFAULT
from app.core.security import check_startup_security
from tests.conftest import TEST_PASSWORD


def test_login_succeeds_with_correct_password(anon_client):
    r = anon_client.post("/auth/login", json={"password": TEST_PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["expires_in"] > 0


def test_login_fails_with_wrong_password(anon_client):
    r = anon_client.post("/auth/login", json={"password": "wrong"})
    assert r.status_code == 401


def test_protected_route_requires_token(anon_client):
    # No Authorization header -> rejected.
    r = anon_client.get("/search", params={"query": "Pantop"})
    assert r.status_code == 401


def test_protected_route_rejects_bad_token(anon_client):
    r = anon_client.get(
        "/search",
        params={"query": "Pantop"},
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert r.status_code == 401


def test_protected_route_works_with_token(client):
    # `client` fixture is already authenticated.
    r = client.get("/search", params={"query": "Pantop"})
    assert r.status_code == 200


def test_me_returns_subject(client):
    r = client.get("/auth/me")
    assert r.status_code == 200
    assert r.json()["user"]


def test_health_is_public(anon_client):
    # Health check must not require auth (load balancers hit it).
    assert anon_client.get("/").status_code == 200


# ---------------------------------------------------------------------------
# Login rate limiting (brute-force throttle)
# ---------------------------------------------------------------------------
def test_login_is_rate_limited_after_repeated_failures(anon_client):
    # Default threshold is 5 failures. Each fresh app gets its own limiter, so
    # this test can't leak into others.
    for _ in range(5):
        r = anon_client.post("/auth/login", json={"password": "wrong"})
        assert r.status_code == 401

    # The next attempt is blocked outright — 429 with a Retry-After hint.
    blocked = anon_client.post("/auth/login", json={"password": "wrong"})
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers

    # Even the CORRECT password is rejected while the block is active — that's
    # the whole point of a lockout.
    still_blocked = anon_client.post("/auth/login", json={"password": TEST_PASSWORD})
    assert still_blocked.status_code == 429


def test_successful_login_resets_the_failure_counter(anon_client):
    # Four failures (one under the threshold)...
    for _ in range(4):
        assert anon_client.post("/auth/login", json={"password": "wrong"}).status_code == 401

    # ...then a good login clears the counter.
    assert anon_client.post("/auth/login", json={"password": TEST_PASSWORD}).status_code == 200

    # Four more failures should therefore NOT trip the limiter (counter reset).
    for _ in range(4):
        assert anon_client.post("/auth/login", json={"password": "wrong"}).status_code == 401


# ---------------------------------------------------------------------------
# Startup security guard
# ---------------------------------------------------------------------------
def test_startup_security_passes_with_good_config(auth_env):
    # auth_env sets a real password + non-default signing key.
    assert check_startup_security() == []


def test_startup_security_flags_missing_password(auth_env, monkeypatch):
    monkeypatch.setattr(security, "AUTH_PASSWORD", "")
    problems = check_startup_security()
    assert any("AUTH_PASSWORD" in p for p in problems)


def test_startup_security_flags_insecure_secret(auth_env, monkeypatch):
    monkeypatch.setattr(security, "AUTH_SECRET_KEY", INSECURE_SECRET_DEFAULT)
    problems = check_startup_security()
    assert any("AUTH_SECRET_KEY" in p for p in problems)
