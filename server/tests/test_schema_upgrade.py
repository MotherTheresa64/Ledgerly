from sqlalchemy import text

from app import create_app
from app.extensions import db


def test_existing_user_schema_contains_firebase_identity_mapping():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "JWT_SECRET_KEY": "ledgerly-test-jwt-secret-key-32-bytes-minimum",
        "SECRET_KEY": "ledgerly-test-app-secret-key-32-bytes-minimum",
        "FIREBASE_REQUIRE_VERIFIED_EMAIL": True,
    })
    with app.app_context():
        columns = {row[1] for row in db.session.execute(text('PRAGMA table_info("user")')).all()}
        assert "firebase_uid" in columns
        indexes = db.session.execute(text('PRAGMA index_list("user")')).all()
        assert any(row[1] == "ix_user_firebase_uid" for row in indexes)


def test_fresh_schema_contains_canonical_integer_cent_columns():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "SECRET_KEY": "ledgerly-test-app-secret-key-32-bytes-minimum",
    })
    expected = {
        "financial_account": "opening_balance_cents",
        "transaction": "amount_cents",
        "budget": "limit_cents",
        "goal": "target_cents",
    }
    with app.app_context():
        for table, column in expected.items():
            columns = {row[1]: row[2] for row in db.session.execute(text(f'PRAGMA table_info("{table}")')).all()}
            assert column in columns
            assert "BIGINT" in columns[column].upper()
        goal_columns = {row[1] for row in db.session.execute(text('PRAGMA table_info("goal")')).all()}
        assert "saved_cents" in goal_columns


def test_additive_upgrade_backfills_legacy_float_values(tmp_path):
    database = tmp_path / "legacy-ledgerly.db"
    uri = f"sqlite:///{database.as_posix()}"

    # Reproduce the old production-facing table shapes before the cents migration.
    bootstrap = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": uri, "SECRET_KEY": "bootstrap-secret"})
    with bootstrap.app_context():
        db.drop_all()
        db.session.execute(text('CREATE TABLE "financial_account" (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, name VARCHAR(120) NOT NULL, account_type VARCHAR(32) NOT NULL, opening_balance FLOAT NOT NULL DEFAULT 0, include_in_totals BOOLEAN NOT NULL DEFAULT 1, archived BOOLEAN NOT NULL DEFAULT 0)'))
        db.session.execute(text('CREATE TABLE "transaction" (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, description VARCHAR(180) NOT NULL, amount FLOAT NOT NULL, category VARCHAR(80) NOT NULL, date DATE NOT NULL)'))
        db.session.execute(text('CREATE TABLE "budget" (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, category VARCHAR(80) NOT NULL, "limit" FLOAT NOT NULL)'))
        db.session.execute(text('CREATE TABLE "goal" (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, name VARCHAR(120) NOT NULL, target FLOAT NOT NULL, saved FLOAT NOT NULL DEFAULT 0)'))
        db.session.execute(text('INSERT INTO "financial_account" (id,user_id,name,account_type,opening_balance) VALUES (1,1,\'Checking\',\'checking\',12.34)'))
        db.session.execute(text('INSERT INTO "transaction" (id,user_id,description,amount,category,date) VALUES (1,1,\'Coffee\',-4.56,\'Dining\',\'2026-08-01\')'))
        db.session.execute(text('INSERT INTO "budget" (id,user_id,category,"limit") VALUES (1,1,\'Dining\',100.01)'))
        db.session.execute(text('INSERT INTO "goal" (id,user_id,name,target,saved) VALUES (1,1,\'Trip\',999.99,123.45)'))
        db.session.commit()

    upgraded = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": uri, "SECRET_KEY": "upgrade-secret"})
    with upgraded.app_context():
        assert db.session.execute(text('SELECT opening_balance_cents FROM "financial_account" WHERE id=1')).scalar_one() == 1234
        assert db.session.execute(text('SELECT amount_cents FROM "transaction" WHERE id=1')).scalar_one() == -456
        assert db.session.execute(text('SELECT limit_cents FROM "budget" WHERE id=1')).scalar_one() == 10001
        target, saved = db.session.execute(text('SELECT target_cents, saved_cents FROM "goal" WHERE id=1')).one()
        assert target == 99999
        assert saved == 12345
