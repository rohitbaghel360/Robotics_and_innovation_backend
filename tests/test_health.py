def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["environment"] == "testing"


def test_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["environment"] == "testing"


def test_ready(client):
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
