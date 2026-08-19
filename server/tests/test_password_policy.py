def test_registration_rejects_weak_passwords(client):
    too_short = client.post("/api/auth/register", json={"email": "short@example.com", "password": "abc123"})
    assert too_short.status_code == 400

    no_number = client.post("/api/auth/register", json={"email": "letters@example.com", "password": "onlyletters"})
    assert no_number.status_code == 400

    no_letter = client.post("/api/auth/register", json={"email": "digits@example.com", "password": "1234567890"})
    assert no_letter.status_code == 400
