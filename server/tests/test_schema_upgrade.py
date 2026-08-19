from sqlalchemy import text

from app import create_app
from app.extensions import db


def test_existing_user_schema_is_upgraded_and_grandfathered():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "JWT_SECRET_KEY": "ledgerly-test-jwt-secret-key-32-bytes-minimum",
        "SECRET_KEY": "ledgerly-test-app-secret-key-32-bytes-minimum",
        "EMAIL_VERIFICATION_REQUIRED": True,
    })
    with app.app_context():
        # create_app already creates the modern schema; this assertion protects the fields the runtime migration expects.
        columns = {row[1] for row in db.session.execute(text('PRAGMA table_info("user")')).all()}
        assert {
            "email_verified_at",
            "verification_nonce",
            "verification_sent_at",
            "password_reset_nonce",
            "password_reset_sent_at",
            "password_changed_at",
            "auth_version",
        }.issubset(columns)
