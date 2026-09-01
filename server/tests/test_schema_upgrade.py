import sqlite3
from decimal import Decimal

import sqlalchemy as sa
from flask_migrate import upgrade

from app import create_app
from app.extensions import db
from app.models import FinancialAccount


def migration_app(database_path):
    return create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}",
        "SECRET_KEY": "ledgerly-test-app-secret-key-32-bytes-minimum",
        "FIREBASE_REQUIRE_VERIFIED_EMAIL": True,
    })


def test_migration_builds_fresh_schema_with_decimal_money(tmp_path):
    database_path = tmp_path / "fresh.db"
    app = migration_app(database_path)
    with app.app_context():
        upgrade(directory="migrations")
        inspector = sa.inspect(db.engine)
        assert {"user", "financial_account", "transaction", "budget", "goal"}.issubset(set(inspector.get_table_names()))
        assert isinstance({c["name"]: c for c in inspector.get_columns("transaction")}["amount"]["type"], sa.Numeric)
        assert isinstance({c["name"]: c for c in inspector.get_columns("budget")}["limit"]["type"], sa.Numeric)
        assert isinstance({c["name"]: c for c in inspector.get_columns("goal")}["target"]["type"], sa.Numeric)


def test_migration_upgrades_legacy_float_schema_without_dropping_data(tmp_path):
    database_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(database_path)
    connection.executescript("""
        CREATE TABLE user (
            id INTEGER PRIMARY KEY,
            email VARCHAR(180) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            created_at DATETIME NOT NULL
        );
        CREATE TABLE financial_account (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            name VARCHAR(120) NOT NULL,
            account_type VARCHAR(32) NOT NULL,
            institution VARCHAR(120),
            opening_balance FLOAT NOT NULL,
            description VARCHAR(500),
            include_in_totals BOOLEAN NOT NULL,
            archived BOOLEAN NOT NULL,
            created_at DATETIME NOT NULL
        );
        CREATE TABLE "transaction" (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            description VARCHAR(180) NOT NULL,
            amount FLOAT NOT NULL,
            category VARCHAR(80) NOT NULL,
            date DATE NOT NULL,
            notes TEXT
        );
        CREATE TABLE budget (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            category VARCHAR(80) NOT NULL,
            "limit" FLOAT NOT NULL
        );
        CREATE TABLE goal (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            name VARCHAR(120) NOT NULL,
            target FLOAT NOT NULL,
            saved FLOAT NOT NULL
        );
        INSERT INTO user (id, email, password_hash, created_at)
        VALUES (1, 'legacy@example.com', 'placeholder', '2026-08-01 00:00:00');
        INSERT INTO financial_account
            (id, user_id, name, account_type, institution, opening_balance, description, include_in_totals, archived, created_at)
        VALUES (1, 1, 'Legacy card', 'credit', '', 500.55, '', 1, 0, '2026-08-01 00:00:00');
        INSERT INTO "transaction" (id, user_id, description, amount, category, date, notes)
        VALUES (1, 1, 'Legacy purchase', -10.10, 'Shopping', '2026-08-15', '');
        INSERT INTO budget (id, user_id, category, "limit") VALUES (1, 1, 'Shopping', 100.10);
        INSERT INTO goal (id, user_id, name, target, saved) VALUES (1, 1, 'Legacy goal', 1000.10, 100.10);
    """)
    connection.commit()
    connection.close()

    app = migration_app(database_path)
    with app.app_context():
        upgrade(directory="migrations")
        inspector = sa.inspect(db.engine)
        transaction_columns = {column["name"]: column for column in inspector.get_columns("transaction")}
        assert {"account_id", "transaction_type", "subcategory", "tags", "transfer_group"}.issubset(transaction_columns)
        assert isinstance(transaction_columns["amount"]["type"], sa.Numeric)

        account = db.session.get(FinancialAccount, 1)
        assert account is not None
        assert account.opening_balance == Decimal("-500.55")
        migrated_tx = db.session.execute(sa.text('SELECT amount, transaction_type FROM "transaction" WHERE id = 1')).one()
        assert Decimal(str(migrated_tx.amount)).quantize(Decimal("0.01")) == Decimal("-10.10")
        assert migrated_tx.transaction_type == "expense"
