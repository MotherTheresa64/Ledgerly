import os


def database_url():
    value = os.getenv("DATABASE_URL", "sqlite:///ledgerly.db")
    if value.startswith("postgres://"):
        value = value.replace("postgres://", "postgresql+psycopg://", 1)
    elif value.startswith("postgresql://"):
        value = value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value


def env_bool(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
    # Flask-JWT remains initialized only so legacy route imports stay harmless during migration.
    # Production authorization is Firebase-only.
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "legacy-jwt-not-used-for-production-auth")
    SQLALCHEMY_DATABASE_URI = database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False
    FIREBASE_REQUIRE_VERIFIED_EMAIL = env_bool("FIREBASE_REQUIRE_VERIFIED_EMAIL", True)
