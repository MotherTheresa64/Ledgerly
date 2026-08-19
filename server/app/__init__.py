import os
from flask import Flask
from flask_cors import CORS
from .config import Config
from .extensions import db, jwt
from .routes import api


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    jwt.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": os.getenv("CLIENT_ORIGIN", "http://localhost:5173")}})
    app.register_blueprint(api)

    with app.app_context():
        db.create_all()

    return app
