import pytest
from app import create_app
from app.extensions import db


def firebase_headers(email="demo@example.com", uid="demo-uid"):
    return {"Authorization": f"Bearer test-firebase:{uid}:{email}"}


@pytest.fixture()
def app():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "JWT_SECRET_KEY": "ledgerly-test-secret-key-32-bytes-minimum",
        "SECRET_KEY": "ledgerly-test-app-secret-key-32-bytes-minimum",
        "FIREBASE_REQUIRE_VERIFIED_EMAIL": True,
    })
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_headers():
    return firebase_headers()
