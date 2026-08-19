from app import create_app
from app.extensions import db
from app.models import User
from app.routes import password_reset_token, verification_token


def secure_app():
    return create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "JWT_SECRET_KEY": "ledgerly-test-jwt-secret-key-32-bytes-minimum",
        "SECRET_KEY": "ledgerly-test-app-secret-key-32-bytes-minimum",
        "EMAIL_VERIFICATION_REQUIRED": True,
        "AUTH_EMAIL_COOLDOWN_SECONDS": 0,
    })


def test_registration_requires_email_verification():
    app = secure_app()
    client = app.test_client()
    with app.app_context():
        db.create_all()

    response = client.post("/api/auth/register", json={"email": "verify@example.com", "password": "password123"})
    assert response.status_code == 201
    assert response.get_json()["verificationRequired"] is True
    assert "accessToken" not in response.get_json()

    login = client.post("/api/auth/login", json={"email": "verify@example.com", "password": "password123"})
    assert login.status_code == 403
    assert login.get_json()["code"] == "email_unverified"

    with app.app_context():
        user = User.query.filter_by(email="verify@example.com").one()
        token = verification_token(user)

    verified = client.post("/api/auth/verify-email", json={"token": token})
    assert verified.status_code == 200
    assert verified.get_json()["verified"] is True
    access_token = verified.get_json()["accessToken"]

    account = client.get("/api/account", headers={"Authorization": f"Bearer {access_token}"})
    assert account.status_code == 200
    assert account.get_json()["emailVerified"] is True

    reused = client.post("/api/auth/verify-email", json={"token": token})
    assert reused.status_code == 400

    with app.app_context():
        db.drop_all()


def test_password_reset_is_single_use_and_revokes_existing_sessions():
    app = secure_app()
    client = app.test_client()
    with app.app_context():
        db.create_all()

    client.post("/api/auth/register", json={"email": "reset@example.com", "password": "password123"})
    with app.app_context():
        user = User.query.filter_by(email="reset@example.com").one()
        verify = verification_token(user)
    verified = client.post("/api/auth/verify-email", json={"token": verify})
    old_access_token = verified.get_json()["accessToken"]

    forgot = client.post("/api/auth/forgot-password", json={"email": "reset@example.com"})
    assert forgot.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email="reset@example.com").one()
        reset = password_reset_token(user)

    changed = client.post("/api/auth/reset-password", json={"token": reset, "newPassword": "newpassword456"})
    assert changed.status_code == 200

    stale = client.get("/api/dashboard", headers={"Authorization": f"Bearer {old_access_token}"})
    assert stale.status_code == 401

    old_login = client.post("/api/auth/login", json={"email": "reset@example.com", "password": "password123"})
    assert old_login.status_code == 401
    new_login = client.post("/api/auth/login", json={"email": "reset@example.com", "password": "newpassword456"})
    assert new_login.status_code == 200

    reused = client.post("/api/auth/reset-password", json={"token": reset, "newPassword": "anotherpass789"})
    assert reused.status_code == 400

    with app.app_context():
        db.drop_all()


def test_forgot_password_does_not_reveal_account_existence():
    app = secure_app()
    client = app.test_client()
    with app.app_context():
        db.create_all()

    missing = client.post("/api/auth/forgot-password", json={"email": "missing@example.com"})
    assert missing.status_code == 200
    assert "If an account exists" in missing.get_json()["message"]

    with app.app_context():
        db.drop_all()
