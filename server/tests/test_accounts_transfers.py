from datetime import date


def firebase_headers(email, uid):
    return {"Authorization": f"Bearer test-firebase:{uid}:{email}"}


def create_account(client, headers, name, account_type="checking", opening=0):
    response = client.post("/api/accounts", headers=headers, json={
        "name": name,
        "type": account_type,
        "openingBalance": opening,
        "includeInTotals": True,
    })
    assert response.status_code == 201
    return response.get_json()


def test_accounts_affect_balances_and_are_private(client):
    owner = firebase_headers("owner-accounts@example.com", "owner-accounts")
    other = firebase_headers("other-accounts@example.com", "other-accounts")
    checking = create_account(client, owner, "Checking", opening=500)

    created = client.post("/api/transactions", headers=owner, json={
        "description": "Paycheck",
        "amount": 1000,
        "transactionType": "income",
        "accountId": checking["id"],
        "category": "Income",
        "date": date.today().isoformat(),
    })
    assert created.status_code == 201

    dashboard = client.get("/api/dashboard", headers=owner).get_json()
    assert dashboard["accounts"][0]["currentBalance"] == 1500
    assert dashboard["totalBalance"] == 1500
    assert client.get("/api/accounts", headers=other).get_json() == []
    assert client.patch(f"/api/accounts/{checking['id']}", headers=other, json={"name": "Stolen"}).status_code == 404


def test_transfer_moves_balance_without_changing_cash_flow(client, auth_headers):
    checking = create_account(client, auth_headers, "Checking", opening=1000)
    savings = create_account(client, auth_headers, "Savings", "savings", opening=200)
    response = client.post("/api/transfers", headers=auth_headers, json={
        "fromAccountId": checking["id"],
        "toAccountId": savings["id"],
        "amount": 250,
        "date": date.today().isoformat(),
        "description": "Monthly savings",
    })
    assert response.status_code == 201
    payload = response.get_json()
    assert len(payload["transactions"]) == 2

    dashboard = client.get("/api/dashboard", headers=auth_headers).get_json()
    by_name = {item["name"]: item for item in dashboard["accounts"]}
    assert by_name["Checking"]["currentBalance"] == 750
    assert by_name["Savings"]["currentBalance"] == 450
    assert dashboard["income"] == 0
    assert dashboard["expenses"] == 0
    assert dashboard["netCashFlow"] == 0
    assert dashboard["totalBalance"] == 1200

    delete = client.delete(f"/api/transactions/{payload['transactions'][0]['id']}", headers=auth_headers)
    assert delete.status_code == 200
    dashboard = client.get("/api/dashboard", headers=auth_headers).get_json()
    assert [item for item in dashboard["transactions"] if item["transactionType"] == "transfer"] == []


def test_partial_import_skips_invalid_and_duplicate_rows(client, auth_headers):
    account = create_account(client, auth_headers, "Import Checking")
    existing = {
        "description": "Rent",
        "amount": -850,
        "transactionType": "expense",
        "accountId": account["id"],
        "category": "Housing",
        "date": "2026-08-01",
    }
    assert client.post("/api/transactions", headers=auth_headers, json=existing).status_code == 201

    response = client.post("/api/transactions/import", headers=auth_headers, json={
        "allowPartial": True,
        "defaultAccountId": account["id"],
        "transactions": [
            {"description": "Rent", "amount": -850, "category": "Housing", "date": "2026-08-01"},
            {"description": "Broken", "amount": 0, "category": "Other", "date": "bad-date"},
            {"description": "Groceries", "amount": -125, "category": "Groceries", "date": "2026-08-02"},
        ],
    })
    assert response.status_code == 201
    payload = response.get_json()
    assert payload["imported"] == 1
    assert payload["invalidRows"] == [2]
    assert payload["skippedDuplicates"] == [1]


def test_goal_target_date_and_monthly_plan_shape(client, auth_headers):
    goal = client.post("/api/goals", headers=auth_headers, json={
        "name": "Emergency fund",
        "target": 5000,
        "saved": 1000,
        "targetDate": "2027-08-31",
        "notes": "Keep this informational.",
    })
    assert goal.status_code == 201
    assert goal.get_json()["targetDate"] == "2027-08-31"
    assert goal.get_json()["amountRemaining"] == 4000

    dashboard = client.get("/api/dashboard", headers=auth_headers).get_json()
    plan = dashboard["monthlyPlan"]
    for key in ["expectedIncome", "actualIncome", "budgetedExpenses", "actualExpenses", "amountRemaining", "unbudgetedSpending", "savingsContribution", "netResult", "daysRemaining"]:
        assert key in plan
