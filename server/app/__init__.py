import os
from uuid import uuid4

from flask import Flask, g, jsonify, request
from flask_cors import CORS
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .extensions import db
from .money import MoneyValidationError, to_cents
from .routes import api

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


def _add_columns(table_name, additions):
    inspector = inspect(db.engine)
    if not inspector.has_table(table_name):
        return set()
    existing = {column["name"] for column in inspector.get_columns(table_name)}
    added = set()
    for name, definition in additions.items():
        if name not in existing:
            db.session.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN {name} {definition}'))
            added.add(name)
    return added


def ensure_finance_schema():
    """Apply additive upgrades and backfill exact integer-cent storage.

    Legacy FLOAT columns remain as compatibility mirrors so an existing Render/Postgres
    deployment can migrate in place. All current application calculations use the new
    BIGINT cent columns.
    """
    inspector = inspect(db.engine)

    if inspector.has_table("financial_account"):
        _add_columns("financial_account", {"opening_balance_cents": "BIGINT NOT NULL DEFAULT 0"})
        db.session.execute(text(
            'UPDATE "financial_account" SET opening_balance_cents = '
            'CAST(ROUND(opening_balance * 100) AS BIGINT) '
            'WHERE opening_balance_cents = 0 AND opening_balance <> 0'
        ))

    if inspector.has_table("transaction"):
        _add_columns("transaction", {
            "account_id": "INTEGER",
            "transaction_type": "VARCHAR(16)",
            "subcategory": "VARCHAR(80)",
            "tags": "VARCHAR(500)",
            "transfer_group": "VARCHAR(64)",
            "amount_cents": "BIGINT NOT NULL DEFAULT 0",
        })
        db.session.execute(text(
            'UPDATE "transaction" SET amount_cents = CAST(ROUND(amount * 100) AS BIGINT) '
            'WHERE amount_cents = 0 AND amount <> 0'
        ))
        db.session.execute(text(
            "UPDATE \"transaction\" SET transaction_type = "
            "CASE WHEN amount_cents >= 0 THEN 'income' ELSE 'expense' END "
            "WHERE transaction_type IS NULL OR transaction_type = ''"
        ))
        db.session.execute(text('CREATE INDEX IF NOT EXISTS ix_transaction_account_id ON "transaction" (account_id)'))
        db.session.execute(text('CREATE INDEX IF NOT EXISTS ix_transaction_transfer_group ON "transaction" (transfer_group)'))

    if inspector.has_table("budget"):
        _add_columns("budget", {"limit_cents": "BIGINT NOT NULL DEFAULT 0"})
        db.session.execute(text(
            'UPDATE "budget" SET limit_cents = CAST(ROUND("limit" * 100) AS BIGINT) '
            'WHERE limit_cents = 0 AND "limit" <> 0'
        ))

    if inspector.has_table("goal"):
        _add_columns("goal", {
            "target_date": "DATE",
            "notes": "TEXT",
            "target_cents": "BIGINT NOT NULL DEFAULT 0",
            "saved_cents": "BIGINT NOT NULL DEFAULT 0",
        })
        db.session.execute(text(
            'UPDATE "goal" SET target_cents = CAST(ROUND(target * 100) AS BIGINT) '
            'WHERE target_cents = 0 AND target <> 0'
        ))
        db.session.execute(text(
            'UPDATE "goal" SET saved_cents = CAST(ROUND(saved * 100) AS BIGINT) '
            'WHERE saved_cents = 0 AND saved <> 0'
        ))

    db.session.commit()


def invalid_money_value(payload):
    """Return a validation message for malformed monetary values anywhere in JSON."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in MONEY_FIELDS:
                label = key.replace("_", " ").replace("Balance", " balance").strip().capitalize()
                try:
                    to_cents(value, label=label)
                except MoneyValidationError as error:
                    return str(error)
            nested = invalid_money_value(value)
            if nested:
                return nested
    elif isinstance(payload, list):
        for item in payload:
            nested = invalid_money_value(item)
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


def _cors_origins():
    configured = os.getenv("CLIENT_ORIGIN", "http://localhost:5173")
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


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
        resources={r"/api/*": {"origins": _cors_origins()}},
        supports_credentials=False,
    )
    app.register_blueprint(api)

    @app.before_request
    def validate_api_request():
        g.request_id = request.headers.get("X-Request-ID") or uuid4().hex

        if request.path.startswith("/api/auth/"):
            return jsonify({"error": "Authentication is managed by Firebase Authentication."}), 410
        if request.path == "/api/account/password":
            return jsonify({"error": "Password changes are managed by Firebase Authentication."}), 410

        if request.path.startswith("/api/") and request.method in {"POST", "PUT", "PATCH"} and request.is_json:
            payload = request.get_json(silent=True)
            money_error = invalid_money_value(payload)
            if money_error:
                return jsonify({"error": money_error}), 400
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
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        response.headers.setdefault("X-Request-ID", getattr(g, "request_id", ""))
        if request.is_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if response.mimetype == "application/json":
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.errorhandler(413)
    def payload_too_large(_error):
        return jsonify({"error": "Request body is too large."}), 413

    @app.errorhandler(HTTPException)
    def http_error(error):
        message = {
            404: "The requested resource was not found.",
            405: "That HTTP method is not supported for this resource.",
            415: "Requests with a body must use application/json.",
        }.get(error.code, error.description or "Request failed.")
        return jsonify({"error": message}), error.code

    @app.errorhandler(SQLAlchemyError)
    def database_error(error):
        db.session.rollback()
        app.logger.exception("Database operation failed", exc_info=error)
        return jsonify({"error": "Ledgerly could not complete the database operation. Please try again."}), 500

    @app.errorhandler(Exception)
    def unexpected_error(error):
        db.session.rollback()
        app.logger.exception("Unhandled API error", exc_info=error)
        return jsonify({"error": "Ledgerly encountered an unexpected error. Please try again."}), 500

    with app.app_context():
        db.create_all()
        ensure_auth_schema()
        ensure_finance_schema()

    return app
