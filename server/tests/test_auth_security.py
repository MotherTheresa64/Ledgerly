from app.extensions import db
from app.models import Transaction, User


def headers(uid, email):
    return {"Authorization": f"Bearer test-firebase:{uid}:{email}"}


def test_firebase_identity_is_created_on_first_api_request(client, app):
    response = client.get("/api/account", headers=headers("firebase-123", "verify@example.com"))
    assert response.status_code == 200
    assert response.get_json()["email"] == "verify@example.com"
    assert response.get_json()["emailVerified"] is True

    with app.app_context():
        user = User.query.filter_by(email="verify@example.com").one()
        assert user.firebase_uid == "firebase-123"


def test_existing_ledgerly_email_links_to_verified_firebase_identity(client, app):
    with app.app_context():
        legacy = User(email="legacy@example.com")
        legacy.set_password("legacy-password-123")
        db.session.add(legacy)
        db.session.commit()
        db.session.add(Transaction(user_id=legacy.id, description="Existing data", amount=-12, category="Other"))
        db.session.commit()

    response = client.get("/api/dashboard", headers=headers("firebase-migrated", "legacy@example.com"))
    assert response.status_code == 200
    assert len(response.get_json()["transactions"]) == 1

    with app.app_context():
        linked = User.query.filter_by(email="legacy@example.com").one()
        assert linked.firebase_uid == "firebase-migrated"


def test_same_email_cannot_be_claimed_by_second_firebase_uid(client):
    first = client.get("/api/account", headers=headers("uid-one", "owner@example.com"))
    assert first.status_code == 200
    second = client.get("/api/account", headers=headers("uid-two", "owner@example.com"))
    assert second.status_code == 401


def test_invalid_bearer_token_is_rejected(client):
    response = client.get("/api/dashboard", headers={"Authorization": "Bearer definitely-not-firebase"})
    assert response.status_code == 401


def test_legacy_auth_and_password_recovery_are_not_served_by_flask(client):
    for path in ["/api/auth/register", "/api/auth/login", "/api/auth/forgot-password", "/api/auth/reset-password", "/api/auth/verify-email"]:
        response = client.post(path, json={})
        assert response.status_code == 410
        assert "Firebase" in response.get_json()["error"]
