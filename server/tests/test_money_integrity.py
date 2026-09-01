from decimal import Decimal

from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import Transaction


def firebase_headers(email, uid):
    return {"Authorization": f"Bearer test-firebase:{uid}:{email}"}


def create_account(client, headers, name, account_type="checking", opening="0.00"):
    response = client.post("/api/accounts", headers=headers, json={
        "name": name,
        "type": account_type,
        "openingBalance": opening,
        "includeInTotals": True,
    })
    assert response.status_code == 201
    return response.get_json()


def test_decimal_cents_and_rounding_never_accumulate_binary_float_error(client, auth_headers):
    account = create_account(client, auth_headers, "Precision")
    for index in range(100):
        response = client.post("/api/transactions", headers=auth_headers, json={
            "description": f"Cent {index}",
            "amount": "0.01",
            "transactionType": "income",
            "accountId": account["id"],
            "category": "Income",
            "date": "2026-09-01",
        })
        assert response.status_code == 201

    rounded = client.post("/api/transactions", headers=auth_headers, json={
        "description": "Half cent",
        "amount": "1.005",
        "transactionType": "income",
        "accountId": account["id"],
        "category": "Income",
        "date": "2026-09-01",
    })
    assert rounded.status_code == 201
    assert rounded.get_json()["amount"] == 1.01

    ten_ten = client.post("/api/transactions", headers=auth_headers, json={
        "description": "Ten ten",
        "amount": "10.10",
        "transactionType": "income",
        "accountId": account["id"],
        "category": "Income",
        "date": "2026-09-01",
    })
    assert ten_ten.status_code == 201
    assert ten_ten.get_json()["amount"] == 10.10

    dashboard = client.get("/api/dashboard", headers=auth_headers).get_json()
    assert dashboard["totalBalance"] == 12.11

    with client.application.app_context():
        stored = db.session.query(Transaction.amount).filter(Transaction.description == "Half cent").scalar()
        assert isinstance(stored, Decimal)
        assert stored == Decimal("1.01")


def test_invalid_non_decimal_money_literals_are_rejected(client, auth_headers):
    for value in ["NaN", "Infinity", "-Infinity", "1e2"]:
        response = client.post("/api/transactions", headers=auth_headers, json={
            "description": "Unsafe amount",
            "amount": value,
            "category": "Other",
            "date": "2026-09-01",
        })
        assert response.status_code == 400


def test_maximum_supported_money_value_is_deliberate(client, auth_headers):
    accepted = client.post("/api/transactions", headers=auth_headers, json={
        "description": "Maximum",
        "amount": "999999999.99",
        "transactionType": "income",
        "category": "Income",
        "date": "2026-09-01",
    })
    assert accepted.status_code == 201

    rejected = client.post("/api/transactions", headers=auth_headers, json={
        "description": "Too large",
        "amount": "1000000000.00",
        "transactionType": "income",
        "category": "Income",
        "date": "2026-09-01",
    })
    assert rejected.status_code == 400


def test_liability_balances_and_net_worth_semantics(client, auth_headers):
    checking = create_account(client, auth_headers, "Checking", opening="1000.00")
    credit = create_account(client, auth_headers, "Card", "credit", opening="500.00")
    assert credit["balanceRole"] == "liability"
    assert credit["openingBalance"] == 500.0
    assert credit["currentBalance"] == -500.0

    dashboard = client.get("/api/dashboard", headers=auth_headers).get_json()
    assert dashboard["netWorth"] == 500.0
    assert dashboard["assetBalance"] == 1000.0
    assert dashboard["liabilityBalance"] == 500.0

    purchase = client.post("/api/transactions", headers=auth_headers, json={
        "description": "Card purchase",
        "amount": "100.00",
        "transactionType": "expense",
        "accountId": credit["id"],
        "category": "Groceries",
        "date": "2026-09-01",
    })
    assert purchase.status_code == 201

    payment = client.post("/api/transfers", headers=auth_headers, json={
        "fromAccountId": checking["id"],
        "toAccountId": credit["id"],
        "amount": "200.00",
        "date": "2026-09-01",
        "description": "Card payment",
    })
    assert payment.status_code == 201

    dashboard = client.get("/api/dashboard", headers=auth_headers).get_json()
    by_name = {item["name"]: item for item in dashboard["accounts"]}
    assert by_name["Checking"]["currentBalance"] == 800.0
    assert by_name["Card"]["currentBalance"] == -400.0
    assert dashboard["netWorth"] == 400.0
    assert dashboard["income"] == 0
    assert dashboard["expenses"] == 100.0
    assert dashboard["netCashFlow"] == -100.0


def test_category_matching_is_case_and_whitespace_insensitive(client, auth_headers):
    expense = client.post("/api/transactions", headers=auth_headers, json={
        "description": "Food",
        "amount": "12.34",
        "transactionType": "expense",
        "category": "  Groceries   ",
        "date": "2026-09-01",
    })
    assert expense.status_code == 201

    first = client.post("/api/budgets", headers=auth_headers, json={"category": "groceries", "limit": "100.00"})
    assert first.status_code == 201
    payload = first.get_json()
    assert payload["spent"] == 12.34

    second = client.post("/api/budgets", headers=auth_headers, json={"category": "  GROCERIES ", "limit": "200.00"})
    assert second.status_code == 200
    assert second.get_json()["id"] == payload["id"]
    assert second.get_json()["spent"] == 12.34


def test_goal_overfunding_is_preserved_and_explained(client, auth_headers):
    created = client.post("/api/goals", headers=auth_headers, json={"name": "Trip", "target": "100.00", "saved": "90.00"})
    goal_id = created.get_json()["id"]
    contributed = client.post(f"/api/goals/{goal_id}/contribute", headers=auth_headers, json={"amount": "20.00"})
    assert contributed.status_code == 200
    payload = contributed.get_json()
    assert payload["saved"] == 110.0
    assert payload["percentComplete"] == 110.0
    assert payload["amountRemaining"] == 0.0
    assert payload["isOverfunded"] is True
    assert payload["overfundedBy"] == 10.0
    assert payload["trackingOnly"] is True


def test_transfer_failure_rolls_back_both_entries(client, auth_headers, monkeypatch):
    source = create_account(client, auth_headers, "Source", opening="100.00")
    destination = create_account(client, auth_headers, "Destination")
    original_flush = db.session.flush

    def fail_transfer_flush(*args, **kwargs):
        new_items = list(db.session.new)
        if len([item for item in new_items if isinstance(item, Transaction) and item.transfer_group]) >= 2:
            raise SQLAlchemyError("simulated insert failure")
        return original_flush(*args, **kwargs)

    monkeypatch.setattr(db.session, "flush", fail_transfer_flush)
    response = client.post("/api/transfers", headers=auth_headers, json={
        "fromAccountId": source["id"],
        "toAccountId": destination["id"],
        "amount": "10.00",
        "date": "2026-09-01",
    })
    assert response.status_code == 500

    with client.application.app_context():
        assert Transaction.query.filter_by(transaction_type="transfer").count() == 0


def test_transfer_ids_are_user_scoped_and_transfer_accounts_cannot_be_hard_deleted(client):
    owner = firebase_headers("owner-transfer@example.com", "owner-transfer")
    other = firebase_headers("other-transfer@example.com", "other-transfer")
    source = create_account(client, owner, "Owner source", opening="100.00")
    destination = create_account(client, owner, "Owner destination")

    denied = client.post("/api/transfers", headers=other, json={
        "fromAccountId": source["id"],
        "toAccountId": destination["id"],
        "amount": "10.00",
        "date": "2026-09-01",
    })
    assert denied.status_code == 400

    created = client.post("/api/transfers", headers=owner, json={
        "fromAccountId": source["id"],
        "toAccountId": destination["id"],
        "amount": "10.00",
        "date": "2026-09-01",
    })
    assert created.status_code == 201

    blocked = client.delete(f"/api/accounts/{source['id']}?detach=true", headers=owner)
    assert blocked.status_code == 409
    assert "historical transfers" in blocked.get_json()["error"]


def test_import_decimal_fingerprints_are_predictable(client, auth_headers):
    payload = {
        "transactions": [
            {"description": "Decimal import", "amount": "10.10", "transactionType": "income", "category": "Income", "date": "2026-09-01"},
            {"description": "Decimal import", "amount": "10.100", "transactionType": "income", "category": " income ", "date": "2026-09-01"},
        ]
    }
    response = client.post("/api/transactions/import", headers=auth_headers, json=payload)
    assert response.status_code == 201
    assert response.get_json()["imported"] == 1
    assert response.get_json()["skippedDuplicates"] == [2]
    assert response.get_json()["importMode"] == "atomic"
