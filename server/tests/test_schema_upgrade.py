from sqlalchemy import text

from app import create_app
from app.extensions import db


def test_existing_user_schema_contains_firebase_identity_mapping():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "JWT_SECRET_KEY": "ledgerly-test-jwt-secret-key-32-bytes-minimum",
        "SECRET_KEY": "ledgerly-test-app-secret-key-32-bytes-minimum",
        "FIREBASE_REQUIRE_VERIFIED_EMAIL": True,
    })
    with app.app_context():
        columns = {row[1] for row in db.session.execute(text('PRAGMA table_info("user")')).all()}
        assert "firebase_uid" in columns
        indexes = db.session.execute(text('PRAGMA index_list("user")')).all()
        assert any(row[1] == "ix_user_firebase_uid" for row in indexes)
