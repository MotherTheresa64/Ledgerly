def register(client, email, password="password123"):
    response = client.post("/api/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.get_json()['accessToken']}"}


def test_account_summary_and_password_change(client, auth_headers):
    account = client.get("/api/account", headers=auth_headers)
    assert account.status_code == 200
    assert account.get_json()["email"] == "demo@example.com"

    bad = client.patch("/api/account/password", headers=auth_headers, json={"currentPassword": "wrong", "newPassword": "newpassword123"})
    assert bad.status_code == 403

    changed = client.patch("/api/account/password", headers=auth_headers, json={"currentPassword": "password123", "newPassword": "newpassword123"})
    assert changed.status_code == 200
    assert client.post("/api/auth/login", json={"email": "demo@example.com", "password": "password123"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "demo@example.com", "password": "newpassword123"}).status_code == 200


def test_transaction_import_is_atomic(client, auth_headers):
    valid = [
        {"description": "Paycheck", "amount": 2000, "category": "Income", "date": "2026-08-10", "notes": "August"},
        {"description": "Rent", "amount": -850, "category": "Housing", "date": "2026-08-11", "notes": ""},
    ]
    response = client.post("/api/transactions/import", headers=auth_headers, json={"transactions": valid})
    assert response.status_code == 201
    assert response.get_json()["imported"] == 2

    before = client.get("/api/dashboard", headers=auth_headers).get_json()["transactions"]
    invalid = [
        {"description": "Valid row", "amount": -20, "category": "Other", "date": "2026-08-12"},
        {"description": "Broken", "amount": 0, "category": "Other", "date": "not-a-date"},
    ]
    response = client.post("/api/transactions/import", headers=auth_headers, json={"transactions": invalid})
    assert response.status_code == 400
    after = client.get("/api/dashboard", headers=auth_headers).get_json()["transactions"]
    assert len(after) == len(before)


def test_user_data_isolation(client):
    first = register(client, "first@example.com")
    second = register(client, "second@example.com")
    created = client.post("/api/transactions", headers=first, json={"description": "Private", "amount": -25, "category": "Other", "date": "2026-08-18"})
    tx_id = created.get_json()["id"]

    second_dashboard = client.get("/api/dashboard", headers=second).get_json()
    assert second_dashboard["transactions"] == []
    assert client.delete(f"/api/transactions/{tx_id}", headers=second).status_code == 404
    assert client.patch(f"/api/transactions/{tx_id}", headers=second, json={"description": "Hack", "amount": -1, "category": "Other", "date": "2026-08-18"}).status_code == 404


def test_demo_reset_and_clear_data(client, auth_headers):
    client.post("/api/transactions", headers=auth_headers, json={"description": "Old", "amount": -10, "category": "Other", "date": "2026-08-18"})
    reset = client.post("/api/demo/reset", headers=auth_headers)
    assert reset.status_code == 200
    dashboard = client.get("/api/dashboard", headers=auth_headers).get_json()
    assert len(dashboard["monthlyTrend"]) == 6
    assert len(dashboard["transactions"]) > 20
    assert len(dashboard["budgets"]) == 4
    assert len(dashboard["goals"]) == 2

    cleared = client.delete("/api/data", headers=auth_headers)
    assert cleared.status_code == 200
    dashboard = client.get("/api/dashboard", headers=auth_headers).get_json()
    assert dashboard["transactions"] == []
    assert dashboard["budgets"] == []
    assert dashboard["goals"] == []


def test_delete_account_requires_password(client, auth_headers):
    denied = client.delete("/api/account", headers=auth_headers, json={"password": "wrong"})
    assert denied.status_code == 403
    deleted = client.delete("/api/account", headers=auth_headers, json={"password": "password123"})
    assert deleted.status_code == 200
    assert client.post("/api/auth/login", json={"email": "demo@example.com", "password": "password123"}).status_code == 401
