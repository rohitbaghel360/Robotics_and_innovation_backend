"""Auth routing and validation tests.

These exercise the request/validation layer and auth guards without a live
database, so they run anywhere (including CI without MySQL).
"""


def test_register_rejects_short_password(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "name": "Test User", "password": "short"},
    )
    assert resp.status_code == 422


def test_register_rejects_missing_name(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "securepass1"},
    )
    assert resp.status_code == 422


def test_register_rejects_invalid_email(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "name": "Test User", "password": "securepass1"},
    )
    assert resp.status_code == 422


def test_login_requires_payload(client):
    resp = client.post("/api/v1/auth/login", json={})
    assert resp.status_code == 422


def test_me_requires_authentication(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_rejects_invalid_token(client):
    resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert resp.status_code == 401
