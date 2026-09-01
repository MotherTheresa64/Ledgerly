from app.extensions import db
from app.models import Transaction


def test_decimal_currency_aggregates_without_float_drift(client, auth_headers):
    for index in range(10):
        response = client.post("/api/transactions", headers=auth_headers, json={
            "description": f"Micro purchase {index}",
            "amount": "-0.10",
            "transactionType": "expense",
            "category": "Other",
            "date": "2026-08-15",
        })
        assert response.status_code == 201

    dashboard = client.get("/api/dashboard?asOf=2026-08-15", headers=auth_headers).get_json()
    assert dashboard["expenses"] == 1.00
    assert dashboard["netCashFlow"] == -1.00
    assert dashboard["totalBalance"] == -1.00


def test_rejects_more_than_two_decimal_places(client, auth_headers):
    response = client.post("/api/transactions", headers=auth_headers, json={
        "description": "Fractional cent",
        "amount": "-10.001",
        "category": "Other",
        "date": "2026-08-15",
    })
    assert response.status_code == 400
    assert "two decimal places" in response.get_json()["error"]


def test_partial_import_can_skip_invalid_money_row(client, auth_headers):
    response = client.post("/api/transactions/import", headers=auth_headers, json={
        "allowPartial": True,
        "transactions": [
            {"description": "Valid", "amount": "-12.34", "category": "Other", "date": "2026-08-15"},
            {"description": "Fractional cent", "amount": "-1.999", "category": "Other", "date": "2026-08-15"},
            {"description": "Also valid", "amount": "5.67", "category": "Income", "date": "2026-08-16"},
        ],
    })
    assert response.status_code == 201
    assert response.get_json()["imported"] == 2
    assert response.get_json()["invalidRows"] == [2]


def test_budget_over_100_percent_remains_numerically_correct(client, auth_headers):
    budget = client.post("/api/budgets", headers=auth_headers, json={"category": "Dining", "limit": "100.00"})
    assert budget.status_code == 201
    expense = client.post("/api/transactions", headers=auth_headers, json={
        "description": "Dinner",
        "amount": "-250.25",
        "transactionType": "expense",
        "category": "Dining",
        "date": "2026-08-20",
    })
    assert expense.status_code == 201

    dashboard = client.get("/api/dashboard?asOf=2026-08-20", headers=auth_headers).get_json()
    dining = next(item for item in dashboard["budgets"] if item["category"] == "Dining")
    assert dining["spent"] == 250.25
    assert dining["remaining"] == -150.25
    assert dining["percentUsed"] == 250.25
    assert dining["status"] == "over"


def test_as_of_date_controls_month_boundaries(client, auth_headers):
    for description, amount, tx_date in [
        ("August income", 1000, "2026-08-31"),
        ("September income", 2000, "2026-09-01"),
    ]:
        response = client.post("/api/transactions", headers=auth_headers, json={
            "description": description,
            "amount": amount,
            "transactionType": "income",
            "category": "Income",
            "date": tx_date,
        })
        assert response.status_code == 201

    august = client.get("/api/dashboard?asOf=2026-08-31", headers=auth_headers).get_json()
    september = client.get("/api/dashboard?asOf=2026-09-01", headers=auth_headers).get_json()
    assert august["income"] == 1000
    assert september["income"] == 2000
    assert august["asOf"] == "2026-08-31"
    assert september["asOf"] == "2026-09-01"


def test_legacy_orm_write_populates_cents(app):
    with app.app_context():
        from app.models import User

        user = User(email="legacy-money@example.com")
        user.set_legacy_placeholder("not-used")
        db.session.add(user)
        db.session.flush()
        transaction = Transaction(
            user_id=user.id,
            description="Legacy write",
            amount=-12.34,
            category="Other",
        )
        db.session.add(transaction)
        db.session.commit()
        assert transaction.amount_cents == -1234
        assert transaction.to_dict()["amount"] == -12.34


def test_missing_resource_returns_safe_json(client, auth_headers):
    response = client.delete("/api/transactions/999999", headers=auth_headers)
    assert response.status_code == 404
    assert response.is_json
    assert response.get_json() == {"error": "The requested resource was not found."}
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers.get("X-Request-ID")
