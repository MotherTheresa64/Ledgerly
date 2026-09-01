import os

from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .extensions import db, migrate
from .money import MoneyValidationError, parse_money
from .routes import api

MONEY_FIELDS = {"amount", "limit", "target", "saved", "openingBalance", "opening_balance"}
MAX_TRANSACTION_DESCRIPTION = 80
MAX_TRANSACTION_NOTES = 500


def invalid_money_field(payload):
    """Return the first malformed money field in a JSON payload."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in MONEY_FIELDS:
                try:
                    parse_money(value)
                except MoneyValidationError:
                    return key
            nested = invalid_money_field(value)
            if nested:
                return nested
    elif isinstance(payload, list):
        for item in payload:
            nested = invalid_money_field(item)
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
    # Alembic/Flask-Migrate is the durable schema authority. Batch mode keeps the same
    # migration history usable for local SQLite development and PostgreSQL production.
    migrate.init_app(app, db, compare_type=True, render_as_batch=True)
    CORS(
        app,
        resources={r"/api/*": {"origins": os.getenv("CLIENT_ORIGIN", "http://localhost:5173")}},
        supports_credentials=False,
        allow_headers=["Authorization", "Content-Type"],
        methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    )
    app.register_blueprint(api)

    @app.before_request
    def validate_api_request():
        if request.path.startswith("/api/auth/"):
            return jsonify({"error": "Authentication is managed by Firebase Authentication."}), 410
        if request.path == "/api/account/password":
            return jsonify({"error": "Password changes are managed by Firebase Authentication."}), 410

        if request.path.startswith("/api/") and request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.is_json:
            payload = request.get_json(silent=True)
            money_field = invalid_money_field(payload)
            if money_field:
                label = money_field.replace("_", " ").replace("openingBalance", "opening balance").capitalize()
                return jsonify({"error": f"{label} must be a finite decimal amount between -$999,999,999.99 and $999,999,999.99; scientific notation is not accepted."}), 400
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
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
        if response.mimetype == "application/json":
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.errorhandler(413)
    def payload_too_large(_error):
        return jsonify({"error": "Request body is too large."}), 413

    @app.errorhandler(500)
    def internal_error(_error):
        db.session.rollback()
        return jsonify({"error": "Ledgerly could not complete that request."}), 500

    return app
