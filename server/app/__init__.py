import os

from flask import Flask
from flask_cors import CORS
from sqlalchemy import inspect, text

from .config import Config
from .extensions import db, jwt
from .models import User
from .routes import api


def ensure_auth_schema():
    inspector = inspect(db.engine)
    if not inspector.has_table("user"):
        return

    existing = {column["name"] for column in inspector.get_columns("user")}
    additions = {
        "email_verified_at": "TIMESTAMP",
        "verification_nonce": "VARCHAR(96)",
        "verification_sent_at": "TIMESTAMP",
        "password_reset_nonce": "VARCHAR(96)",
        "password_reset_sent_at": "TIMESTAMP",
        "password_changed_at": "TIMESTAMP",
        "auth_version": "INTEGER NOT NULL DEFAULT 0",
    }
    added_verification_column = "email_verified_at" not in existing
    for name, definition in additions.items():
        if name not in existing:
            db.session.execute(text(f'ALTER TABLE "user" ADD COLUMN {name} {definition}'))
    if added_verification_column:
        # Accounts created before verification shipped are grandfathered in so a deploy never locks them out.
        db.session.execute(text('UPDATE "user" SET email_verified_at = CURRENT_TIMESTAMP WHERE email_verified_at IS NULL'))
    db.session.commit()


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    jwt.init_app(app)
    CORS(
        app,
        resources={r"/api/*": {"origins": os.getenv("CLIENT_ORIGIN", "http://localhost:5173")}},
        supports_credentials=False,
    )
    app.register_blueprint(api)

    @jwt.token_in_blocklist_loader
    def token_is_revoked(_jwt_header, jwt_payload):
        try:
            user_id = int(jwt_payload.get("sub", 0))
            token_version = int(jwt_payload.get("av", -1))
        except (TypeError, ValueError):
            return True
        user = db.session.get(User, user_id)
        if not user:
            return True
        if app.config.get("EMAIL_VERIFICATION_REQUIRED", True) and not user.email_verified:
            return True
        return int(user.auth_version or 0) != token_version

    with app.app_context():
        db.create_all()
        ensure_auth_schema()

    return app
