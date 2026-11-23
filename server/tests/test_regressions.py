from datetime import date

from app.extensions import db
from app.firebase_auth import _ledgerly_user_for_claims
from app.models import User


def headers(uid, email):
    return {"Authorization": f"Bearer test-firebase:{uid}:{email}"}


def test_unverified_identity_never_links_to_existing_email_even_when_check_is_relaxed(app):
    app.config["FIREBASE_REQUIRE_VERIFIED_EMAIL"] = False
    legacy = User(email="victim@example.com")
    legacy.set_legacy_placeholder("placeholder-secret-value")
    db.session.add(legacy)
    db.session.commit()

    claims = {"uid": "attacker-uid", "email": "victim@example.com", "email_verified": False}
    with app.test_request_context():
        assert _ledgerly_user_for_claims(claims) is None
    assert db.session.get(User, legacy.id).firebase_uid is None


def create_tx(client, h, **extra):
    body = {"description": "Coffee", "amount": 4.5, "transactionType": "expense",
            "category": "Food", "date": date.today().isoformat(), **extra}
    response = client.post("/api/transactions", headers=h, json=body)
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def test_transaction_on_archived_account_can_still_be_corrected(client):
    h = headers("archive-uid", "archive@example.com")
    account = client.post("/api/accounts", headers=h, json={
        "name": "Old Checking", "type": "checking", "openingBalance": 0, "includeInTotals": True,
    }).get_json()
    tx = create_tx(client, h, accountId=account["id"])
    assert client.patch(f"/api/accounts/{account['id']}", headers=h, json={"archived": True}).status_code == 200

    fixed = client.patch(f"/api/transactions/{tx['id']}", headers=h, json={
        "description": "Coffee beans", "amount": 4.5, "transactionType": "expense",
        "category": "Food", "date": tx["date"], "accountId": account["id"],
    })
    assert fixed.status_code == 200, fixed.get_json()
    assert fixed.get_json()["description"] == "Coffee beans"

    new_on_archived = client.post("/api/transactions", headers=h, json={
        "description": "New", "amount": 1, "transactionType": "expense",
        "category": "Food", "date": tx["date"], "accountId": account["id"],
    })
    assert new_on_archived.status_code == 400


def test_patch_keeps_optional_fields_that_were_not_sent(client):
    h = headers("patch-uid", "patch@example.com")
    tx = create_tx(client, h, notes="receipt in drawer", tags=["work"], subcategory="Cafe")

    response = client.patch(f"/api/transactions/{tx['id']}", headers=h, json={
        "description": "Coffee", "amount": 6, "transactionType": "expense",
        "category": "Food", "date": tx["date"],
    })
    assert response.status_code == 200
    body = response.get_json()
    assert body["notes"] == "receipt in drawer"
    assert body["subcategory"] == "Cafe"
    assert body["amount"] == -6


def test_budget_counts_spend_regardless_of_category_case(client):
    h = headers("budget-case-uid", "budget-case@example.com")
    assert client.post("/api/budgets", headers=h, json={"category": "groceries", "limit": 100}).status_code == 201
    create_tx(client, h, category="Groceries", amount=30)
    budget = client.get("/api/budgets", headers=h).get_json()[0]
    assert budget["spent"] == 30
