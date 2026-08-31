import math
import os

from flask import Flask, jsonify, request
from flask_cors import CORS
from sqlalchemy import inspect, text
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .extensions import db
from .routes import api

MAX_MONEY = 999_999_999.99
MONEY_FIELDS = {"amount", "limit", "target", "saved", "openingBalance", "opening_balance"}
MAX_TRANSACTION_DESCRIPTION = 80
MAX_TRANSACTION_NOTES = 500


def ensure_auth_schema():
    inspector = inspect(db.engine)
    if not inspector.has_table("user"):
        return

    existing = {column["name"] for column in inspector.get_columns("user")}
    additions = {
        "firebase_uid": "VARCHAR(128)",
        "email_verified_at": "TIMESTAMP",
        "verification_nonce": "VARCHAR(96)",
        "verification_sent_at": "TIMESTAMP",
        "password_reset_nonce": "VARCHAR(96)",
        "password_reset_sent_at": "TIMESTAMP",
        "password_changed_at": "TIMESTAMP",
        "auth_version": "INTEGER NOT NULL DEFAULT 0",
    }
    for name, definition in additions.items():
        if name not in existing:
            db.session.execute(text(f'ALTER TABLE "user" ADD COLUMN {name} {definition}'))
    db.session.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS ix_user_firebase_uid ON "user" (firebase_uid)'))
    db.session.commit()


def ensure_finance_schema():
    """Apply additive production-safe upgrades without rewriting existing user data."""
    inspector = inspect(db.engine)

    if inspector.has_table("transaction"):
        existing = {column["name"] for column in inspector.get_columns("transaction")}
        additions = {
            "account_id": "INTEGER",
            "transaction_type": "VARCHAR(16)",
            "subcategory": "VARCHAR(80)",
            "tags": "VARCHAR(500)",
            "transfer_group": "VARCHAR(64)",
        }
        for name, definition in additions.items():
            if name not in existing:
                db.session.execute(text(f'ALTER TABLE "transaction" ADD COLUMN {name} {definition}'))
        db.session.execute(text(
            "UPDATE \"transaction\" SET transaction_type = "
            "CASE WHEN amount >= 0 THEN 'income' ELSE 'expense' END "
            "WHERE transaction_type IS NULL OR transaction_type = ''"
        ))
        db.session.execute(text('CREATE INDEX IF NOT EXISTS ix_transaction_account_id ON "transaction" (account_id)'))
        db.session.execute(text('CREATE INDEX IF NOT EXISTS ix_transaction_transfer_group ON "transaction" (transfer_group)'))

    if inspector.has_table("goal"):
        existing = {column["name"] for column in inspector.get_columns("goal")}
        additions = {"target_date": "DATE", "notes": "TEXT"}
        for name, definition in additions.items():
            if name not in existing:
                db.session.execute(text(f'ALTER TABLE "goal" ADD COLUMN {name} {definition}'))

    db.session.commit()


def oversized_money_value(payload):
    """Return the first monetary field that exceeds Ledgerly's supported range."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in MONEY_FIELDS:
                try:
                    number = float(value)
                except (TypeError, ValueError):
                    continue
                if not math.isfinite(number) or abs(number) > MAX_MONEY:
                    return key
            nested = oversized_money_value(value)
            if nested:
                return nested
    elif isinstance(payload, list):
        for item in payload:
            nested = oversized_money_value(item)
            if nested:
                return nested
    return None


def oversized_transaction_text(payload):
    """Return a validation message when transaction text exceeds UI-safe limits."""
    if isinstance(payload, dict):
        if "description" in payload and len(str(payload.get("description") or "").strip()) > MAX_TRANSACTION_DESCRIPTION:
            return f"Description cannot exceed {MAX_TRANSACTION_DESCRIPTION} characters."
        if "notes" in payload and len(str(payload.get("notes") or "").strip()) > MAX_TRANSACTION_NOTES:
            return f"Notes cannot exceed {MAX_TRANSACTION_NOTES} characters."
        for value in payload.values():
            nested = oversized_transaction_text(value)
            if nested:
                return nested
    elif isinstance(payload, list):
        for item in payload:
            nested = oversized_transaction_text(item)
            if nested:
                return nested
    return None


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.config.setdefault("MAX_CONTENT_LENGTH", 2 * 1024 * 1024)

    db.init_app(app)
    CORS(
        app,
        resources={r"/api/*": {"origins": os.getenv("CLIENT_ORIGIN", "http://localhost:5173")}},
        supports_credentials=False,
    )
    app.register_blueprint(api)

    @app.before_request
    def validate_api_request():
        if request.path.startswith("/api/auth/"):
            return jsonify({"error": "Authentication is managed by Firebase Authentication."}), 410
        if request.path == "/api/account/password":
            return jsonify({"error": "Password changes are managed by Firebase Authentication."}), 410

        if request.path.startswith("/api/") and request.method in {"POST", "PUT", "PATCH"} and request.is_json:
            payload = request.get_json(silent=True)
            oversized_field = oversized_money_value(payload)
            if oversized_field:
                return jsonify({"error": f"{oversized_field.replace('_', ' ').capitalize()} cannot exceed $999,999,999.99."}), 400
            if request.path.startswith("/api/transactions") or request.path.startswith("/api/transfers"):
                text_error = oversized_transaction_text(payload)
                if text_error:
                    return jsonify({"error": text_error}), 400
        return None

    @app.after_request
    def secure_api_response(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if response.mimetype == "application/json":
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.errorhandler(413)
    def payload_too_large(_error):
        return jsonify({"error": "Request body is too large."}), 413

    with app.app_context():
        db.create_all()
        ensure_auth_schema()
        ensure_finance_schema()

    return app
