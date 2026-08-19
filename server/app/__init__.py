import os

from flask import Flask, jsonify
from flask_cors import CORS
from sqlalchemy import inspect, text
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .extensions import db, jwt
from .models import User
from .rate_limit import install_auth_rate_limits
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

    # Render terminates TLS in front of Gunicorn. Trust exactly one proxy hop for the real client IP/protocol.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.config.setdefault("MAX_CONTENT_LENGTH", 2 * 1024 * 1024)

    db.init_app(app)
    jwt.init_app(app)
    CORS(
        app,
        resources={r"/api/*": {"origins": os.getenv("CLIENT_ORIGIN", "http://localhost:5173")}},
        supports_credentials=False,
    )
    install_auth_rate_limits(api)
    app.register_blueprint(api)

    @app.after_request
    def secure_api_response(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if request_path_is_api(response):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.errorhandler(413)
    def payload_too_large(_error):
        return jsonify({"error": "Request body is too large."}), 413

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


def request_path_is_api(response):
    # CORS and the application itself only expose API responses from this service.
    # Checking for the JSON mimetype avoids attaching cache policy to Gunicorn/Render error pages.
    return response.mimetype == "application/json"
