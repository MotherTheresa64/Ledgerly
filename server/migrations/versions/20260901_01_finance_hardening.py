"""establish durable finance schema and decimal money

Revision ID: 20260901_01
Revises:
Create Date: 2026-09-01

This first durable migration is intentionally adaptive because Ledgerly previously evolved
its production schema with additive startup ALTER TABLE statements. It supports both a
fresh database and an existing PostgreSQL/SQLite database without dropping user data.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260901_01"
down_revision = None
branch_labels = None
depends_on = None

MONEY = sa.Numeric(14, 2)


def _columns(bind, table):
    return {column["name"]: column for column in sa.inspect(bind).get_columns(table)}


def _indexes(bind, table):
    return {index["name"] for index in sa.inspect(bind).get_indexes(table)}


def _tables(bind):
    return set(sa.inspect(bind).get_table_names())


def _ensure_index(bind, table, name, columns, unique=False):
    if name not in _indexes(bind, table):
        op.create_index(name, table, columns, unique=unique)


def _alter_money_column(bind, table, column):
    existing = _columns(bind, table)[column]
    if isinstance(existing["type"], sa.Numeric) and getattr(existing["type"], "scale", None) == 2:
        return
    if bind.dialect.name == "postgresql":
        op.execute(sa.text(
            f'ALTER TABLE "{table}" ALTER COLUMN "{column}" TYPE NUMERIC(14,2) '
            f'USING ROUND(CAST("{column}" AS NUMERIC), 2)'
        ))
    else:
        with op.batch_alter_table(table) as batch:
            batch.alter_column(
                column,
                existing_type=existing["type"],
                type_=MONEY,
                existing_nullable=existing.get("nullable", True),
            )


def _create_fresh_schema(bind):
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(180), nullable=False),
        sa.Column("firebase_uid", sa.String(128), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_user_email", "user", ["email"], unique=True)
    op.create_index("ix_user_firebase_uid", "user", ["firebase_uid"], unique=True)

    op.create_table(
        "financial_account",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("account_type", sa.String(32), nullable=False),
        sa.Column("institution", sa.String(120), nullable=True),
        sa.Column("opening_balance", MONEY, nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("include_in_totals", sa.Boolean(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_financial_account_user_id", "financial_account", ["user_id"])
    op.create_index("ix_financial_account_account_type", "financial_account", ["account_type"])
    op.create_index("ix_financial_account_archived", "financial_account", ["archived"])

    op.create_table(
        "transaction",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("financial_account.id"), nullable=True),
        sa.Column("description", sa.String(180), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("transaction_type", sa.String(16), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("subcategory", sa.String(80), nullable=True),
        sa.Column("tags", sa.String(500), nullable=True),
        sa.Column("transfer_group", sa.String(64), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    for name, columns in [
        ("ix_transaction_user_id", ["user_id"]),
        ("ix_transaction_account_id", ["account_id"]),
        ("ix_transaction_transaction_type", ["transaction_type"]),
        ("ix_transaction_category", ["category"]),
        ("ix_transaction_transfer_group", ["transfer_group"]),
        ("ix_transaction_date", ["date"]),
    ]:
        op.create_index(name, "transaction", columns)

    op.create_table(
        "budget",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("limit", MONEY, nullable=False),
    )
    op.create_index("ix_budget_user_id", "budget", ["user_id"])

    op.create_table(
        "goal",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("target", MONEY, nullable=False),
        sa.Column("saved", MONEY, nullable=False),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_goal_user_id", "goal", ["user_id"])


def upgrade():
    bind = op.get_bind()
    tables = _tables(bind)
    if not tables.intersection({"user", "financial_account", "transaction", "budget", "goal"}):
        _create_fresh_schema(bind)
        return

    if "user" not in tables:
        raise RuntimeError("Existing Ledgerly finance tables require the user table before migration can continue.")

    user_columns = _columns(bind, "user")
    with op.batch_alter_table("user") as batch:
        if "firebase_uid" not in user_columns:
            batch.add_column(sa.Column("firebase_uid", sa.String(128), nullable=True))
        if "email_verified_at" not in user_columns:
            batch.add_column(sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    _ensure_index(bind, "user", "ix_user_firebase_uid", ["firebase_uid"], unique=True)
    _ensure_index(bind, "user", "ix_user_email", ["email"], unique=True)

    if "financial_account" not in _tables(bind):
        op.create_table(
            "financial_account",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("account_type", sa.String(32), nullable=False),
            sa.Column("institution", sa.String(120), nullable=True),
            sa.Column("opening_balance", MONEY, nullable=False),
            sa.Column("description", sa.String(500), nullable=True),
            sa.Column("include_in_totals", sa.Boolean(), nullable=False),
            sa.Column("archived", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
    else:
        _alter_money_column(bind, "financial_account", "opening_balance")
    for name, columns in [
        ("ix_financial_account_user_id", ["user_id"]),
        ("ix_financial_account_account_type", ["account_type"]),
        ("ix_financial_account_archived", ["archived"]),
    ]:
        _ensure_index(bind, "financial_account", name, columns)

    # Existing Ledgerly releases treated opening balances as signed user input but did not
    # define liability semantics. Under v1.3 credit/loan debt is negative internally.
    op.execute(sa.text(
        "UPDATE financial_account SET opening_balance = -opening_balance "
        "WHERE account_type IN ('credit', 'loan') AND opening_balance > 0"
    ))

    if "transaction" not in _tables(bind):
        op.create_table(
            "transaction",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
            sa.Column("account_id", sa.Integer(), sa.ForeignKey("financial_account.id"), nullable=True),
            sa.Column("description", sa.String(180), nullable=False),
            sa.Column("amount", MONEY, nullable=False),
            sa.Column("transaction_type", sa.String(16), nullable=False),
            sa.Column("category", sa.String(80), nullable=False),
            sa.Column("subcategory", sa.String(80), nullable=True),
            sa.Column("tags", sa.String(500), nullable=True),
            sa.Column("transfer_group", sa.String(64), nullable=True),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
        )
    else:
        tx_columns = _columns(bind, "transaction")
        with op.batch_alter_table("transaction") as batch:
            if "account_id" not in tx_columns:
                batch.add_column(sa.Column("account_id", sa.Integer(), nullable=True))
            if "transaction_type" not in tx_columns:
                batch.add_column(sa.Column("transaction_type", sa.String(16), nullable=True))
            if "subcategory" not in tx_columns:
                batch.add_column(sa.Column("subcategory", sa.String(80), nullable=True))
            if "tags" not in tx_columns:
                batch.add_column(sa.Column("tags", sa.String(500), nullable=True))
            if "transfer_group" not in tx_columns:
                batch.add_column(sa.Column("transfer_group", sa.String(64), nullable=True))
        _alter_money_column(bind, "transaction", "amount")
        op.execute(sa.text(
            "UPDATE \"transaction\" SET transaction_type = "
            "CASE WHEN amount >= 0 THEN 'income' ELSE 'expense' END "
            "WHERE transaction_type IS NULL OR transaction_type = ''"
        ))
        tx_columns = _columns(bind, "transaction")
        if tx_columns["transaction_type"].get("nullable", True):
            with op.batch_alter_table("transaction") as batch:
                batch.alter_column("transaction_type", existing_type=sa.String(16), nullable=False)

    for name, columns in [
        ("ix_transaction_user_id", ["user_id"]),
        ("ix_transaction_account_id", ["account_id"]),
        ("ix_transaction_transaction_type", ["transaction_type"]),
        ("ix_transaction_category", ["category"]),
        ("ix_transaction_transfer_group", ["transfer_group"]),
        ("ix_transaction_date", ["date"]),
    ]:
        _ensure_index(bind, "transaction", name, columns)

    if "budget" not in _tables(bind):
        op.create_table(
            "budget",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
            sa.Column("category", sa.String(80), nullable=False),
            sa.Column("limit", MONEY, nullable=False),
        )
    else:
        _alter_money_column(bind, "budget", "limit")
    _ensure_index(bind, "budget", "ix_budget_user_id", ["user_id"])

    if "goal" not in _tables(bind):
        op.create_table(
            "goal",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("target", MONEY, nullable=False),
            sa.Column("saved", MONEY, nullable=False),
            sa.Column("target_date", sa.Date(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
        )
    else:
        goal_columns = _columns(bind, "goal")
        with op.batch_alter_table("goal") as batch:
            if "target_date" not in goal_columns:
                batch.add_column(sa.Column("target_date", sa.Date(), nullable=True))
            if "notes" not in goal_columns:
                batch.add_column(sa.Column("notes", sa.Text(), nullable=True))
        _alter_money_column(bind, "goal", "target")
        _alter_money_column(bind, "goal", "saved")
    _ensure_index(bind, "goal", "ix_goal_user_id", ["user_id"])


def downgrade():
    # The downgrade preserves rows and only relaxes fixed-precision columns back to Float.
    # It intentionally does not reverse liability signs because doing so after new activity
    # would silently change the economic meaning of existing account data.
    bind = op.get_bind()
    for table, column in [
        ("financial_account", "opening_balance"),
        ("transaction", "amount"),
        ("budget", "limit"),
        ("goal", "target"),
        ("goal", "saved"),
    ]:
        if table in _tables(bind) and column in _columns(bind, table):
            existing = _columns(bind, table)[column]
            if bind.dialect.name == "postgresql":
                op.execute(sa.text(
                    f'ALTER TABLE "{table}" ALTER COLUMN "{column}" TYPE DOUBLE PRECISION '
                    f'USING CAST("{column}" AS DOUBLE PRECISION)'
                ))
            else:
                with op.batch_alter_table(table) as batch:
                    batch.alter_column(
                        column,
                        existing_type=existing["type"],
                        type_=sa.Float(),
                        existing_nullable=existing.get("nullable", True),
                    )
