def test_transaction_crud_updates_dashboard(client, auth_headers):
    create = client.post("/api/transactions", headers=auth_headers, json={
        "description": "Paycheck", "amount": 2000, "category": "Income", "date": "2026-08-18", "notes": "August pay"
    })
    assert create.status_code == 201
    transaction_id = create.get_json()["id"]

    expense = client.post("/api/transactions", headers=auth_headers, json={
        "description": "Groceries", "amount": -150, "category": "Food & Dining", "date": "2026-08-18"
    })
    assert expense.status_code == 201

    dashboard = client.get("/api/dashboard", headers=auth_headers).get_json()
    assert dashboard["income"] == 2000
    assert dashboard["expenses"] == 150
    assert dashboard["totalBalance"] == 1850
    assert len(dashboard["monthlyTrend"]) == 6

    updated = client.patch(f"/api/transactions/{transaction_id}", headers=auth_headers, json={
        "description": "Primary paycheck", "amount": 2100, "category": "Income", "date": "2026-08-18", "notes": "Adjusted"
    })
    assert updated.status_code == 200
    assert updated.get_json()["description"] == "Primary paycheck"

    deleted = client.delete(f"/api/transactions/{transaction_id}", headers=auth_headers)
    assert deleted.status_code == 200


def test_rejects_invalid_transaction(client, auth_headers):
    response = client.post("/api/transactions", headers=auth_headers, json={
        "description": "", "amount": 0, "category": "", "date": "bad-date"
    })
    assert response.status_code == 400


def test_demo_seed(client, auth_headers):
    response = client.post("/api/demo/seed", headers=auth_headers)
    assert response.status_code == 201
    dashboard = client.get("/api/dashboard", headers=auth_headers).get_json()
    assert len(dashboard["transactions"]) >= 20
    assert len(dashboard["budgets"]) == 4
    assert len(dashboard["goals"]) == 2
    assert len(dashboard["monthlyTrend"]) == 6
