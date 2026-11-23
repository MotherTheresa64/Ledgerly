import re
from datetime import date

NUMERIC_STRING = re.compile(r"^-?\d+(\.\d+)?$")


def headers():
    return {"Authorization": "Bearer test-firebase:json-uid:json@example.com"}


def numeric_strings(value, path="$"):
    """Money is Decimal internally; every one must leave the API as a JSON number."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield from numeric_strings(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from numeric_strings(item, f"{path}[{index}]")
    elif isinstance(value, str) and NUMERIC_STRING.match(value) and not path.endswith(("id", "Id", "date", "Date")):
        yield path


def test_money_endpoints_return_json_numbers(client):
    h = headers()
    account = client.post("/api/accounts", headers=h, json={"name": "Checking", "type": "checking", "openingBalance": 100.1, "includeInTotals": True}).get_json()
    client.post("/api/transactions", headers=h, json={"description": "Pay", "amount": 1000.2, "transactionType": "income", "category": "Income", "date": date.today().isoformat(), "accountId": account["id"]})
    client.post("/api/transactions", headers=h, json={"description": "Food", "amount": 20.3, "transactionType": "expense", "category": "Food", "date": date.today().isoformat(), "accountId": account["id"]})
    client.post("/api/budgets", headers=h, json={"category": "Food", "limit": 300})
    goal = client.post("/api/goals", headers=h, json={"name": "Trip", "target": 500}).get_json()
    client.post(f"/api/goals/{goal['id']}/contribute", headers=h, json={"amount": 10.1})

    for path in ("/api/dashboard", "/api/accounts", "/api/transactions", "/api/budgets", "/api/goals"):
        body = client.get(path, headers=h).get_json()
        assert list(numeric_strings(body)) == [], path
