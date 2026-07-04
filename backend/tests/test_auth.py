"""Tests for the authentication layer and route protection."""

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
