def test_transaction_updates_dashboard(client, auth_headers):
    create = client.post("/api/transactions", headers=auth_headers, json={"description": "Paycheck", "amount": 2000, "category": "Income", "date": "2026-08-18"})
    assert create.status_code == 201
    expense = client.post("/api/transactions", headers=auth_headers, json={"description": "Groceries", "amount": -150, "category": "Food & Dining", "date": "2026-08-18"})
    assert expense.status_code == 201
    dashboard = client.get("/api/dashboard", headers=auth_headers).get_json()
    assert dashboard["income"] == 2000
    assert dashboard["expenses"] == 150
    assert dashboard["totalBalance"] == 1850


def test_demo_seed(client, auth_headers):
    response = client.post("/api/demo/seed", headers=auth_headers)
    assert response.status_code == 201
    dashboard = client.get("/api/dashboard", headers=auth_headers).get_json()
    assert len(dashboard["transactions"]) > 0
    assert len(dashboard["budgets"]) == 4
    assert len(dashboard["goals"]) == 2
