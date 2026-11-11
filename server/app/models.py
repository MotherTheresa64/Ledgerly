from datetime import UTC, date, datetime

from werkzeug.security import generate_password_hash

from .extensions import db
from .money import cents_to_dollars, legacy_float, to_cents


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    firebase_uid = db.Column(db.String(128), unique=True, nullable=True, index=True)
    # Legacy non-null column retained for in-place production schema compatibility.
    # New credentials live exclusively in Firebase Authentication.
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    email_verified_at = db.Column(db.DateTime(timezone=True), nullable=True)

    @property
    def email_verified(self):
        return self.email_verified_at is not None

    def set_legacy_placeholder(self, value):
        self.password_hash = generate_password_hash(value)


class FinancialAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    account_type = db.Column(db.String(32), nullable=False, default="checking", index=True)
    institution = db.Column(db.String(120), nullable=True)
    # `opening_balance` is retained as a compatibility mirror for existing deployments.
    # `opening_balance_cents` is the canonical value used by all application logic.
    opening_balance = db.Column(db.Float, nullable=False, default=0)
    opening_balance_cents = db.Column(db.BigInteger, nullable=False, default=0)
    description = db.Column(db.String(500), nullable=True)
    include_in_totals = db.Column(db.Boolean, nullable=False, default=True)
    archived = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    def __init__(self, **kwargs):
        if "opening_balance_cents" not in kwargs and "opening_balance" in kwargs:
            kwargs["opening_balance_cents"] = to_cents(kwargs["opening_balance"], label="Opening balance")
        elif "opening_balance_cents" in kwargs and "opening_balance" not in kwargs:
            kwargs["opening_balance"] = legacy_float(int(kwargs["opening_balance_cents"]))
        super().__init__(**kwargs)

    def set_opening_balance_cents(self, cents: int):
        self.opening_balance_cents = int(cents)
        self.opening_balance = legacy_float(cents)


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    account_id = db.Column(db.Integer, db.ForeignKey("financial_account.id"), nullable=True, index=True)
    description = db.Column(db.String(180), nullable=False)
    # `amount` is a compatibility mirror. `amount_cents` is authoritative.
    amount = db.Column(db.Float, nullable=False)
    amount_cents = db.Column(db.BigInteger, nullable=False, default=0)
    transaction_type = db.Column(db.String(16), nullable=False, default="expense", index=True)
    category = db.Column(db.String(80), nullable=False, index=True)
    subcategory = db.Column(db.String(80), nullable=True)
    tags = db.Column(db.String(500), nullable=True)
    transfer_group = db.Column(db.String(64), nullable=True, index=True)
    date = db.Column(db.Date, default=date.today, nullable=False, index=True)
    notes = db.Column(db.Text)

    def __init__(self, **kwargs):
        if "amount_cents" not in kwargs and "amount" in kwargs:
            kwargs["amount_cents"] = to_cents(kwargs["amount"], label="Transaction amount")
        elif "amount_cents" in kwargs and "amount" not in kwargs:
            kwargs["amount"] = legacy_float(int(kwargs["amount_cents"]))
        super().__init__(**kwargs)

    def set_amount_cents(self, cents: int):
        self.amount_cents = int(cents)
        self.amount = legacy_float(cents)

    def to_dict(self, account_name=None):
        amount = cents_to_dollars(self.amount_cents)
        return {
            "id": self.id,
            "description": self.description,
            "amount": amount,
            "transactionType": self.transaction_type or ("income" if self.amount_cents >= 0 else "expense"),
            "accountId": self.account_id,
            "accountName": account_name,
            "category": self.category,
            "subcategory": self.subcategory or "",
            "tags": [tag.strip() for tag in (self.tags or "").split(",") if tag.strip()],
            "transferGroup": self.transfer_group,
            "date": self.date.isoformat(),
            "notes": self.notes or "",
        }


class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    category = db.Column(db.String(80), nullable=False)
    # `limit` is a compatibility mirror. `limit_cents` is authoritative.
    limit = db.Column(db.Float, nullable=False)
    limit_cents = db.Column(db.BigInteger, nullable=False, default=0)

    def __init__(self, **kwargs):
        if "limit_cents" not in kwargs and "limit" in kwargs:
            kwargs["limit_cents"] = to_cents(kwargs["limit"], label="Monthly budget")
        elif "limit_cents" in kwargs and "limit" not in kwargs:
            kwargs["limit"] = legacy_float(int(kwargs["limit_cents"]))
        super().__init__(**kwargs)

    def set_limit_cents(self, cents: int):
        self.limit_cents = int(cents)
        self.limit = legacy_float(cents)


class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    # Legacy FLOAT mirrors are kept through the migration window.
    target = db.Column(db.Float, nullable=False)
    target_cents = db.Column(db.BigInteger, nullable=False, default=0)
    saved = db.Column(db.Float, default=0, nullable=False)
    saved_cents = db.Column(db.BigInteger, default=0, nullable=False)
    target_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    def __init__(self, **kwargs):
        if "target_cents" not in kwargs and "target" in kwargs:
            kwargs["target_cents"] = to_cents(kwargs["target"], label="Goal target")
        elif "target_cents" in kwargs and "target" not in kwargs:
            kwargs["target"] = legacy_float(int(kwargs["target_cents"]))
        if "saved_cents" not in kwargs and "saved" in kwargs:
            kwargs["saved_cents"] = to_cents(kwargs["saved"], label="Saved amount")
        elif "saved_cents" in kwargs and "saved" not in kwargs:
            kwargs["saved"] = legacy_float(int(kwargs["saved_cents"]))
        super().__init__(**kwargs)

    def set_target_cents(self, cents: int):
        self.target_cents = int(cents)
        self.target = legacy_float(cents)

    def set_saved_cents(self, cents: int):
        self.saved_cents = int(cents)
        self.saved = legacy_float(cents)
