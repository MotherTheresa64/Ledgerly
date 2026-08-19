def test_password_policy_is_owned_by_firebase(client):
    response = client.post("/api/auth/register", json={"email": "short@example.com", "password": "abc123"})
    assert response.status_code == 410
    assert "Firebase" in response.get_json()["error"]
