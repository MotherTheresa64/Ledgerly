import os

from flask import Flask, jsonify, request
from flask_cors import CORS
from sqlalchemy import inspect, text
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .extensions import db
from .routes import api


def ensure_auth_schema():
    inspector = inspect(db.engine)
    if not inspector.has_table("user"):
        return

    existing = {column["name"] for column in inspector.get_columns("user")}
    # Keep migrations additive so the existing Render database and local SQLite files
    # remain compatible while Firebase becomes the identity authority.
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
    def firebase_owned_auth_routes():
        if request.path.startswith("/api/auth/"):
            return jsonify({"error": "Authentication is managed by Firebase Authentication."}), 410
        if request.path == "/api/account/password":
            return jsonify({"error": "Password changes are managed by Firebase Authentication."}), 410
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

    return app
