def firebase_headers(email, uid):
    return {"Authorization": f"Bearer test-firebase:{uid}:{email}"}


def test_account_summary_and_password_management_boundary(client, auth_headers):
    account = client.get("/api/account", headers=auth_headers)
    assert account.status_code == 200
    assert account.get_json()["email"] == "demo@example.com"
    assert account.get_json()["emailVerified"] is True

    password = client.patch("/api/account/password", headers=auth_headers, json={"currentPassword": "anything", "newPassword": "anythingelse123"})
    assert password.status_code == 410
    assert "Firebase" in password.get_json()["error"]


def test_transaction_import_is_atomic(client, auth_headers):
    valid = [
        {"description": "Paycheck", "amount": 2000, "category": "Income", "date": "2026-08-10", "notes": "August"},
        {"description": "Rent", "amount": -850, "category": "Housing", "date": "2026-08-11", "notes": ""},
    ]
    response = client.post("/api/transactions/import", headers=auth_headers, json={"transactions": valid})
    assert response.status_code == 201
    assert response.get_json()["imported"] == 2
    assert response.get_json()["importMode"] == "atomic"

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
    first = firebase_headers("first@example.com", "first-uid")
    second = firebase_headers("second@example.com", "second-uid")
    created = client.post("/api/transactions", headers=first, json={"description": "Private", "amount": -25, "category": "Other", "date": "2026-08-18"})
    tx_id = created.get_json()["id"]

    second_dashboard = client.get("/api/dashboard", headers=second).get_json()
    assert second_dashboard["transactions"] == []
    assert client.delete(f"/api/transactions/{tx_id}", headers=second).status_code == 404
    assert client.patch(f"/api/transactions/{tx_id}", headers=second, json={"description": "Hack", "amount": -1, "category": "Other", "date": "2026-08-18"}).status_code == 404


def test_all_financial_resources_are_isolated_between_users(client):
    first = firebase_headers("owner@example.com", "owner-uid")
    second = firebase_headers("other@example.com", "other-uid")

    tx = client.post("/api/transactions", headers=first, json={
        "description": "Private purchase", "amount": -42, "category": "Other", "date": "2026-08-18"
    }).get_json()
    budget = client.post("/api/budgets", headers=first, json={"category": "Other", "limit": 200}).get_json()
    goal = client.post("/api/goals", headers=first, json={"name": "Private goal", "target": 1000, "saved": 100}).get_json()

    other_dashboard = client.get("/api/dashboard", headers=second).get_json()
    assert other_dashboard["transactions"] == []
    assert other_dashboard["budgets"] == []
    assert other_dashboard["goals"] == []
    assert client.get("/api/export", headers=second).get_json()["transactions"] == []

    assert client.delete(f"/api/transactions/{tx['id']}", headers=second).status_code == 404
    assert client.patch(f"/api/budgets/{budget['id']}", headers=second, json={"limit": 1}).status_code == 404
    assert client.delete(f"/api/budgets/{budget['id']}", headers=second).status_code == 404
    assert client.patch(f"/api/goals/{goal['id']}", headers=second, json={"name": "stolen"}).status_code == 404
    assert client.post(f"/api/goals/{goal['id']}/contribute", headers=second, json={"amount": 1}).status_code == 404
    assert client.delete(f"/api/goals/{goal['id']}", headers=second).status_code == 404

    owner_dashboard = client.get("/api/dashboard", headers=first).get_json()
    assert [item["id"] for item in owner_dashboard["transactions"]] == [tx["id"]]
    assert [item["id"] for item in owner_dashboard["budgets"]] == [budget["id"]]
    assert [item["id"] for item in owner_dashboard["goals"]] == [goal["id"]]


def test_destructive_data_routes_require_explicit_confirmation(client, auth_headers):
    client.post("/api/transactions", headers=auth_headers, json={"description": "Keep", "amount": -10, "category": "Other", "date": "2026-08-18"})
    assert client.delete("/api/data", headers=auth_headers).status_code == 400
    assert client.post("/api/demo/reset", headers=auth_headers).status_code == 400
    assert len(client.get("/api/dashboard", headers=auth_headers).get_json()["transactions"]) == 1


def test_clear_data_only_clears_current_user(client):
    first = firebase_headers("first@example.com", "first-clear-uid")
    second = firebase_headers("second@example.com", "second-clear-uid")
    for headers, label in [(first, "First"), (second, "Second")]:
        client.post("/api/transactions", headers=headers, json={"description": label, "amount": -10, "category": "Other", "date": "2026-08-18"})
        client.post("/api/budgets", headers=headers, json={"category": "Other", "limit": 100})
        client.post("/api/goals", headers=headers, json={"name": f"{label} goal", "target": 500, "saved": 50})

    assert client.delete("/api/data", headers=first, json={"confirmation": "CLEAR"}).status_code == 200
    first_dashboard = client.get("/api/dashboard", headers=first).get_json()
    second_dashboard = client.get("/api/dashboard", headers=second).get_json()
    assert first_dashboard["transactions"] == []
    assert first_dashboard["budgets"] == []
    assert first_dashboard["goals"] == []
    assert len(second_dashboard["transactions"]) == 1
    assert len(second_dashboard["budgets"]) == 1
    assert len(second_dashboard["goals"]) == 1


def test_demo_reset_and_clear_data(client, auth_headers):
    client.post("/api/transactions", headers=auth_headers, json={"description": "Old", "amount": -10, "category": "Other", "date": "2026-08-18"})
    reset = client.post("/api/demo/reset", headers=auth_headers, json={"confirmation": "RESET"})
    assert reset.status_code == 200
    assert reset.get_json()["sampleData"] is True
    dashboard = client.get("/api/dashboard", headers=auth_headers).get_json()
    assert len(dashboard["monthlyTrend"]) == 6
    assert len(dashboard["transactions"]) > 20
    assert len(dashboard["budgets"]) == 4
    assert len(dashboard["goals"]) == 2

    cleared = client.delete("/api/data", headers=auth_headers, json={"confirmation": "CLEAR"})
    assert cleared.status_code == 200
    dashboard = client.get("/api/dashboard", headers=auth_headers).get_json()
    assert dashboard["transactions"] == []
    assert dashboard["budgets"] == []
    assert dashboard["goals"] == []


def test_delete_account_removes_ledgerly_and_test_firebase_identity(client, auth_headers):
    client.post("/api/transactions", headers=auth_headers, json={"description": "Private", "amount": -25, "category": "Other", "date": "2026-08-18"})
    assert client.delete("/api/account", headers=auth_headers).status_code == 400
    deleted = client.delete("/api/account", headers=auth_headers, json={"confirmation": "DELETE"})
    assert deleted.status_code == 200
    payload = deleted.get_json()
    assert payload["deleted"] is True
    assert payload["dataDeleted"] is True
    assert payload["firebaseDeleted"] is True
    assert payload["metadataDeleted"] is True
