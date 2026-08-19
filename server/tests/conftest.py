import pytest
from app import create_app
from app.extensions import db


@pytest.fixture()
def app():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "JWT_SECRET_KEY": "ledgerly-test-secret-key-32-bytes-minimum",
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
def auth_headers(client):
    response = client.post("/api/auth/register", json={"email": "demo@example.com", "password": "password123"})
    token = response.get_json()["accessToken"]
    return {"Authorization": f"Bearer {token}"}
