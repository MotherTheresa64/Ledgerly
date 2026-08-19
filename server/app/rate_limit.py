import hashlib
from datetime import UTC, datetime, timedelta

from flask import jsonify, request

from .extensions import db
from .models import AuthRateLimit


AUTH_LIMITS = {
    "/api/auth/register": (8, 3600),
    "/api/auth/login": (20, 900),
    "/api/auth/verify-email": (30, 900),
    "/api/auth/resend-verification": (8, 900),
    "/api/auth/forgot-password": (8, 900),
    "/api/auth/reset-password": (12, 900),
}


def _aware(value):
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _key(path, client_ip):
    return hashlib.sha256(f"{path}|{client_ip}".encode("utf-8")).hexdigest()


def install_auth_rate_limits(blueprint):
    # Blueprints can be registered on many app instances during tests. Install this hook once.
    if getattr(blueprint, "_ledgerly_rate_limits_installed", False):
        return
    blueprint._ledgerly_rate_limits_installed = True

    @blueprint.before_request
    def enforce_auth_rate_limit():
        policy = AUTH_LIMITS.get(request.path)
        if not policy:
            return None

        limit, window_seconds = policy
        client_ip = request.remote_addr or "unknown"
        key = _key(request.path, client_ip)
        now = datetime.now(UTC)
        entry = db.session.get(AuthRateLimit, key)

        if entry is None:
            entry = AuthRateLimit(key=key, window_started_at=now, count=1)
            db.session.add(entry)
            db.session.commit()
            return None

        started = _aware(entry.window_started_at)
        reset_at = started + timedelta(seconds=window_seconds)
        if now >= reset_at:
            entry.window_started_at = now
            entry.count = 1
            db.session.commit()
            return None

        if entry.count >= limit:
            retry_after = max(1, int((reset_at - now).total_seconds()))
            response = jsonify({"error": "Too many authentication attempts. Please try again shortly.", "retryAfter": retry_after})
            response.status_code = 429
            response.headers["Retry-After"] = str(retry_after)
            return response

        entry.count += 1
        db.session.commit()
        return None
