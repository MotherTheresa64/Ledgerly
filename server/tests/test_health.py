def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"] == "no-store"


def test_register_and_login(client):
    register = client.post("/api/auth/register", json={"email": "user@example.com", "password": "password123"})
    assert register.status_code == 201
    login = client.post("/api/auth/login", json={"email": "user@example.com", "password": "password123"})
    assert login.status_code == 200
    assert "accessToken" in login.get_json()
