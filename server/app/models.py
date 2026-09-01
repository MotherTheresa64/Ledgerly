from datetime import UTC, date, datetime
from decimal import Decimal

from werkzeug.security import generate_password_hash

from .extensions import db
from .money import json_money

MONEY_TYPE = db.Numeric(14, 2, asdecimal=True)


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
    opening_balance = db.Column(MONEY_TYPE, nullable=False, default=Decimal("0.00"))
    description = db.Column(db.String(500), nullable=True)
    include_in_totals = db.Column(db.Boolean, nullable=False, default=True)
    archived = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    account_id = db.Column(db.Integer, db.ForeignKey("financial_account.id"), nullable=True, index=True)
    description = db.Column(db.String(180), nullable=False)
    amount = db.Column(MONEY_TYPE, nullable=False)
    transaction_type = db.Column(db.String(16), nullable=False, default="expense", index=True)
    category = db.Column(db.String(80), nullable=False, index=True)
    subcategory = db.Column(db.String(80), nullable=True)
    tags = db.Column(db.String(500), nullable=True)
    transfer_group = db.Column(db.String(64), nullable=True, index=True)
    date = db.Column(db.Date, default=date.today, nullable=False, index=True)
    notes = db.Column(db.Text)

    def to_dict(self, account_name=None):
        return {
            "id": self.id,
            "description": self.description,
            "amount": json_money(self.amount),
            "transactionType": self.transaction_type,
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
    limit = db.Column(MONEY_TYPE, nullable=False)


class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    target = db.Column(MONEY_TYPE, nullable=False)
    saved = db.Column(MONEY_TYPE, default=Decimal("0.00"), nullable=False)
    target_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
