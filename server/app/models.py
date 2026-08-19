from datetime import UTC, date, datetime
from werkzeug.security import check_password_hash, generate_password_hash
from .extensions import db


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    email_verified_at = db.Column(db.DateTime(timezone=True), nullable=True)
    verification_nonce = db.Column(db.String(96), nullable=True)
    verification_sent_at = db.Column(db.DateTime(timezone=True), nullable=True)
    password_reset_nonce = db.Column(db.String(96), nullable=True)
    password_reset_sent_at = db.Column(db.DateTime(timezone=True), nullable=True)
    password_changed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    @property
    def email_verified(self):
        return self.email_verified_at is not None

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        self.password_changed_at = datetime.now(UTC)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    description = db.Column(db.String(180), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(80), nullable=False, index=True)
    date = db.Column(db.Date, default=date.today, nullable=False, index=True)
    notes = db.Column(db.Text)

    def to_dict(self):
        return {"id": self.id, "description": self.description, "amount": self.amount, "category": self.category, "date": self.date.isoformat(), "notes": self.notes or ""}


class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    category = db.Column(db.String(80), nullable=False)
    limit = db.Column(db.Float, nullable=False)


class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    target = db.Column(db.Float, nullable=False)
    saved = db.Column(db.Float, default=0, nullable=False)
