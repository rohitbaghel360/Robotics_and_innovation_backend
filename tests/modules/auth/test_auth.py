def test_register_and_login(client):
    register = client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "securepass1"},
    )
    assert register.status_code == 201
    assert register.json()["email"] == "user@example.com"

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "securepass1"},
    )
    assert login.status_code == 200
    assert "access_token" in login.json()

    token = login.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "user@example.com"


def test_login_invalid_password(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "password": "securepass1"},
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "other@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401


def test_register_duplicate_email(client):
    payload = {"email": "dup@example.com", "password": "securepass1"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    assert client.post("/api/v1/auth/register", json=payload).status_code == 409
