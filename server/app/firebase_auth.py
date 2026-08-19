import json
import os
import secrets
from datetime import UTC, datetime
from functools import wraps

import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials
from flask import current_app, g, jsonify, request

from .extensions import db
from .models import User


def _firebase_app():
    try:
        return firebase_admin.get_app()
    except ValueError:
        raw = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
        project_id = os.getenv("FIREBASE_PROJECT_ID", "").strip()
        if raw:
            info = json.loads(raw)
            return firebase_admin.initialize_app(credentials.Certificate(info), {"projectId": info.get("project_id") or project_id})
        if project_id:
            return firebase_admin.initialize_app(options={"projectId": project_id})
        raise RuntimeError("Firebase Admin is not configured. Set FIREBASE_SERVICE_ACCOUNT_JSON or FIREBASE_PROJECT_ID.")


def _test_claims(token):
    if not current_app.testing:
        return None
    if not token.startswith("test-firebase:"):
        return None
    _, uid, email = token.split(":", 2)
    return {"uid": uid, "email": email, "email_verified": True}


def verify_bearer_token():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    token = header.removeprefix("Bearer ").strip()
    if not token:
        return None

    test_claims = _test_claims(token)
    if test_claims:
        return test_claims

    _firebase_app()
    return firebase_auth.verify_id_token(token, check_revoked=True)


def _ledgerly_user_for_claims(claims):
    uid = str(claims.get("uid") or "").strip()
    email = str(claims.get("email") or "").strip().lower()
    verified = bool(claims.get("email_verified"))
    if not uid or not email:
        return None
    if current_app.config.get("FIREBASE_REQUIRE_VERIFIED_EMAIL", True) and not verified:
        return None

    user = User.query.filter_by(firebase_uid=uid).first()
    if user:
        if user.email != email:
            user.email = email
        if verified and not user.email_verified_at:
            user.email_verified_at = datetime.now(UTC)
        db.session.commit()
        return user

    existing = User.query.filter_by(email=email).first()
    if existing:
        if existing.firebase_uid and existing.firebase_uid != uid:
            return None
        existing.firebase_uid = uid
        if verified and not existing.email_verified_at:
            existing.email_verified_at = datetime.now(UTC)
        db.session.commit()
        return existing

    user = User(email=email, firebase_uid=uid)
    # Legacy local-password storage is retained only for backwards-compatible schema shape;
    # Firebase is the sole credential authority for new accounts.
    user.set_password(secrets.token_urlsafe(48))
    if verified:
        user.email_verified_at = datetime.now(UTC)
    db.session.add(user)
    db.session.commit()
    return user


def authenticate_request():
    try:
        claims = verify_bearer_token()
    except Exception:
        current_app.logger.exception("Firebase token verification failed")
        return None
    if not claims:
        return None
    user = _ledgerly_user_for_claims(claims)
    if not user:
        return None
    g.firebase_claims = claims
    g.ledgerly_user = user
    return user


def firebase_required(fn=None):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not authenticate_request():
                return jsonify({"error": "A valid Firebase session is required."}), 401
            return view(*args, **kwargs)
        return wrapped
    return decorator(fn) if fn else decorator


# Compatibility names let the finance routes keep their established decorators while
# the underlying identity provider is Firebase rather than Flask-JWT-Extended.
def jwt_required():
    return firebase_required()


def get_jwt_identity():
    user = getattr(g, "ledgerly_user", None)
    return str(user.id) if user else None
