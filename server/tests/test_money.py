import sqlite3

from app import create_app
from tests.conftest import firebase_headers

TODAY = __import__("datetime").date.today().isoformat()


def tx(client, headers, amount, **extra):
    body = {"description": "t", "amount": amount, "category": "Food", "date": TODAY, "transactionType": "expense", **extra}
    res = client.post("/api/transactions", json=body, headers=headers)
    assert res.status_code == 201, res.json
    return res.json


def test_sums_are_exact_cents(client, auth_headers):
    acct = client.post("/api/accounts", json={"name": "A", "type": "checking", "openingBalance": 0.1}, headers=auth_headers).json
    client.post("/api/budgets", json={"category": "Food", "limit": 1}, headers=auth_headers)
    tx(client, auth_headers, 0.2, accountId=acct["id"], transactionType="income", category="Pay")
    for _ in range(3):
        tx(client, auth_headers, 0.1, accountId=acct["id"])
    accounts = client.get("/api/accounts", headers=auth_headers).json
    assert accounts[0]["currentBalance"] == 0.0  # 0.1 + 0.2 - 0.3
    dash = client.get("/api/dashboard", headers=auth_headers).json
    assert dash["totalBalance"] == 0.0
    assert dash["income"] == 0.2 and dash["expenses"] == 0.3 and dash["netCashFlow"] == -0.1
    budget = dash["budgets"][0]
    assert budget["spent"] == 0.3 and budget["remaining"] == 0.7


def test_goal_contributions_accumulate_exactly(client, auth_headers):
    goal = client.post("/api/goals", json={"name": "G", "target": 10, "saved": 0.1}, headers=auth_headers).json
    for _ in range(2):
        res = client.post(f"/api/goals/{goal['id']}/contribute", json={"amount": 0.1}, headers=auth_headers)
    assert res.json["saved"] == 0.3
    assert res.json["amountRemaining"] == 9.7


def test_input_rounds_to_cents(client, auth_headers):
    assert tx(client, auth_headers, 10.005)["amount"] == -10.01
    assert tx(client, auth_headers, 1.234)["amount"] == -1.23


def test_legacy_real_columns_still_load(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE user (id INTEGER PRIMARY KEY, email VARCHAR(180) NOT NULL, password_hash VARCHAR(255) NOT NULL, created_at DATETIME NOT NULL);
        CREATE TABLE financial_account (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, name VARCHAR(120) NOT NULL, account_type VARCHAR(32) NOT NULL, institution VARCHAR(120), opening_balance FLOAT NOT NULL, description VARCHAR(500), include_in_totals BOOLEAN NOT NULL, archived BOOLEAN NOT NULL, created_at DATETIME NOT NULL);
        CREATE TABLE "transaction" (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, account_id INTEGER, description VARCHAR(180) NOT NULL, amount FLOAT NOT NULL, transaction_type VARCHAR(16), category VARCHAR(80) NOT NULL, date DATE NOT NULL, notes TEXT);
        CREATE TABLE goal (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, name VARCHAR(120) NOT NULL, target FLOAT NOT NULL, saved FLOAT NOT NULL);
        INSERT INTO user VALUES (1, 'demo@example.com', 'x', '2024-01-01 00:00:00');
        INSERT INTO financial_account VALUES (1, 1, 'A', 'checking', NULL, 0.1, NULL, 1, 0, '2024-01-01 00:00:00');
        INSERT INTO "transaction" VALUES (1, 1, 1, 'a', 0.2, 'income', 'Pay', '2024-01-02', NULL);
        INSERT INTO "transaction" VALUES (2, 1, 1, 'b', -0.1, 'expense', 'Food', '2024-01-03', NULL);
        INSERT INTO goal VALUES (1, 1, 'G', 100.5, 0.30000000000000004);
    """)
    con.commit()
    con.close()
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{path}",
        "SECRET_KEY": "ledgerly-test-app-secret-key-32-bytes-minimum",
        "FIREBASE_REQUIRE_VERIFIED_EMAIL": True,
    })
    client = app.test_client()
    # Same identity the firebase test token maps to is created on first call; reuse user 1 by email.
    from app.extensions import db
    from app.models import User
    with app.app_context():
        User.query.filter_by(id=1).update({"firebase_uid": "demo-uid", "email_verified_at": __import__("datetime").datetime(2024, 1, 1)})
        db.session.commit()
    headers = firebase_headers()
    account = client.get("/api/accounts", headers=headers).json[0]
    assert account["currentBalance"] == 0.2 and account["openingBalance"] == 0.1
    goal = client.get("/api/goals", headers=headers).json[0]
    assert goal["saved"] == 0.3 and goal["target"] == 100.5
