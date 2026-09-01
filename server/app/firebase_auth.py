import json
import os
import secrets
from datetime import UTC, datetime
from functools import wraps

import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials
from flask import current_app, g, jsonify, request
from sqlalchemy.exc import IntegrityError

from .extensions import db
from .models import User


class FirebaseConfigurationError(RuntimeError):
    pass


def _firebase_app():
    try:
        return firebase_admin.get_app()
    except ValueError:
        raw = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
        project_id = os.getenv("FIREBASE_PROJECT_ID", "").strip()
        application_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()

        if raw:
            try:
                info = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise FirebaseConfigurationError("FIREBASE_SERVICE_ACCOUNT_JSON is not valid JSON.") from exc
            resolved_project_id = info.get("project_id") or project_id
            return firebase_admin.initialize_app(credentials.Certificate(info), {"projectId": resolved_project_id})

        if application_credentials:
            return firebase_admin.initialize_app(
                credentials.ApplicationDefault(),
                {"projectId": project_id} if project_id else None,
            )

        if project_id:
            return firebase_admin.initialize_app(options={"projectId": project_id})

        raise FirebaseConfigurationError(
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
    # Unit tests use explicit test-firebase tokens and should not need live Admin
    # credentials merely to verify that an arbitrary bearer value is rejected.
    if current_app.testing:
        return None

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
            collision = User.query.filter(User.email == email, User.id != user.id).first()
            if collision:
                return None
            user.email = email
        if verified and not user.email_verified_at:
            user.email_verified_at = datetime.now(UTC)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return None
        return user

    # Legacy migration is deliberately email-based only after Firebase has proven the
    # address is verified. An address already linked to another UID is never migrated.
    existing = User.query.filter_by(email=email).first()
    if existing:
        if not verified or (existing.firebase_uid and existing.firebase_uid != uid):
            return None
        existing.firebase_uid = uid
        if not existing.email_verified_at:
            existing.email_verified_at = datetime.now(UTC)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return None
        return existing

    user = User(email=email, firebase_uid=uid)
    # The legacy production table retains a non-null password_hash column. The random
    # placeholder is intentionally unusable; Firebase remains the sole credential authority.
    user.set_legacy_placeholder(secrets.token_urlsafe(48))
    if verified:
        user.email_verified_at = datetime.now(UTC)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return None
    return user


def authenticate_request():
    claims = verify_bearer_token()
    if not claims:
        return None
    user = _ledgerly_user_for_claims(claims)
    if not user:
        return None
    g.firebase_claims = claims
    g.ledgerly_user = user
    return user


def delete_firebase_identity(user):
    """Delete the authenticated Firebase identity from the trusted backend.

    Tests intentionally avoid external Firebase calls; production deletion uses the UID
    already bound to the authenticated Ledgerly user, never a client-supplied UID.
    """
    uid = str(user.firebase_uid or "").strip()
    if not uid:
        raise RuntimeError("Ledgerly user has no Firebase UID mapping.")
    if current_app.testing:
        return True
    _firebase_app()
    firebase_auth.delete_user(uid)
    return True


def firebase_required():
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            try:
                user = authenticate_request()
            except FirebaseConfigurationError:
                current_app.logger.error("Firebase Admin is not configured for this environment.")
                return jsonify({"error": "Authentication service is not configured.", "code": "firebase_not_configured"}), 503
            except Exception as exc:
                # Do not log bearer tokens or credential material; exception class is enough for diagnosis.
                current_app.logger.warning("Firebase token verification failed: %s", type(exc).__name__)
                return jsonify({"error": "A valid, verified Firebase session is required."}), 401
            if not user:
                return jsonify({"error": "A valid, verified Firebase session is required."}), 401
            return view(*args, **kwargs)
        return wrapped
    return decorator


def get_jwt_identity():
    """Return the internal Ledgerly user id for finance-domain ownership queries."""
    user = getattr(g, "ledgerly_user", None)
    return str(user.id) if user else None
