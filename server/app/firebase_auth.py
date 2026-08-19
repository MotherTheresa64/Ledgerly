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
        application_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()

        if raw:
            info = json.loads(raw)
            resolved_project_id = info.get("project_id") or project_id
            return firebase_admin.initialize_app(credentials.Certificate(info), {"projectId": resolved_project_id})

        if application_credentials:
            # GOOGLE_APPLICATION_CREDENTIALS points at a Render Secret File. The Google
            # auth stack reads that service-account JSON without exposing its contents as
            # an environment variable or committing credentials to the repository.
            return firebase_admin.initialize_app(
                credentials.ApplicationDefault(),
                {"projectId": project_id} if project_id else None,
            )

        if project_id:
            # Useful on Google-hosted environments that expose Application Default Credentials.
            return firebase_admin.initialize_app(options={"projectId": project_id})

        raise RuntimeError(
            "Firebase Admin is not configured. Set GOOGLE_APPLICATION_CREDENTIALS, "
            "FIREBASE_SERVICE_ACCOUNT_JSON, or FIREBASE_PROJECT_ID with platform credentials."
        )


def _test_claims(token):
    if not current_app.testing or not token.startswith("test-firebase:"):
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
    # The existing production table has a non-null password_hash column from Ledgerly's
    # original local-auth implementation. Store an unusable random placeholder; Firebase
    # is the only credential authority and this value is never checked.
    user.set_legacy_placeholder(secrets.token_urlsafe(48))
    if verified:
        user.email_verified_at = datetime.now(UTC)
    db.session.add(user)
    db.session.commit()
    return user


def authenticate_request():
    try:
        claims = verify_bearer_token()
    except Exception:
        current_app.logger.warning("Firebase token verification failed", exc_info=True)
        return None
    if not claims:
        return None
    user = _ledgerly_user_for_claims(claims)
    if not user:
        return None
    g.firebase_claims = claims
    g.ledgerly_user = user
    return user


def firebase_required():
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not authenticate_request():
                return jsonify({"error": "A valid, verified Firebase session is required."}), 401
            return view(*args, **kwargs)
        return wrapped
    return decorator


def get_jwt_identity():
    """Return the internal Ledgerly user id for finance-domain ownership queries."""
    user = getattr(g, "ledgerly_user", None)
    return str(user.id) if user else None
