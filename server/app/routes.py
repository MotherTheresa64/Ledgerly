from calendar import monthrange
from datetime import date, datetime
import re

from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from sqlalchemy import func

from .extensions import db
from .models import Budget, Goal, Transaction, User

api = Blueprint("api", __name__, url_prefix="/api")

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
MAX_IMPORT_ROWS = 1000


def current_user_id():
    return int(get_jwt_identity())


def current_user():
    return db.session.get(User, current_user_id())


def serialize_goal(goal):
    return {"id": goal.id, "name": goal.name, "target": goal.target, "saved": goal.saved}


def month_keys(count=6):
    today = date.today()
    year, month = today.year, today.month
    items = []
    for _ in range(count):
        items.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(items))


def monthly_trend(transactions):
    result = []
    for year, month in month_keys(6):
        items = [t for t in transactions if t.date.year == year and t.date.month == month]
        income = sum(t.amount for t in items if t.amount > 0)
        expenses = abs(sum(t.amount for t in items if t.amount < 0))
        result.append({
            "month": date(year, month, 1).strftime("%b"),
            "income": round(income, 2),
            "expenses": round(expenses, 2),
            "net": round(income - expenses, 2),
        })
    return result


def current_month_bounds():
    today = date.today()
    return date(today.year, today.month, 1), date(today.year, today.month, monthrange(today.year, today.month)[1])


def clear_financial_data(uid):
    Transaction.query.filter_by(user_id=uid).delete()
    Budget.query.filter_by(user_id=uid).delete()
    Goal.query.filter_by(user_id=uid).delete()


def seed_user(uid):
    months = month_keys(6)
    for index, (year, month) in enumerate(months):
        day = min(18, monthrange(year, month)[1])
        tx_date = date(year, month, day)
        db.session.add(Transaction(user_id=uid, description="Paycheck", amount=3200 + index * 45, category="Income", date=tx_date, notes="Primary income"))
        db.session.add(Transaction(user_id=uid, description="Rent", amount=-1150, category="Housing", date=tx_date, notes="Monthly rent"))
        db.session.add(Transaction(user_id=uid, description="Groceries", amount=-(245 + index * 7.5), category="Food & Dining", date=tx_date))
        db.session.add(Transaction(user_id=uid, description="Utilities", amount=-(185 + index * 4), category="Utilities", date=tx_date))

    today = date.today()
    extras = [
        ("Freelance project", 1450, "Income", "One-off client work"),
        ("Fuel", -96.70, "Transport", "Gas"),
        ("Coffee", -18.64, "Food & Dining", "Coffee with a friend"),
        ("Internet", -79.99, "Utilities", "Home internet"),
        ("Gym", -34.99, "Lifestyle", "Monthly membership"),
    ]
    for description, amount, category, notes in extras:
        db.session.add(Transaction(user_id=uid, description=description, amount=amount, category=category, date=today, notes=notes))

    for category, limit in [("Food & Dining", 500), ("Transport", 250), ("Lifestyle", 200), ("Utilities", 350)]:
        db.session.add(Budget(user_id=uid, category=category, limit=limit))
    db.session.add_all([
        Goal(user_id=uid, name="Emergency fund", target=6000, saved=2450),
        Goal(user_id=uid, name="Weekend trip", target=1200, saved=480),
    ])


def parse_transaction_payload(payload):
    try:
        description = str(payload["description"]).strip()
        amount = float(payload["amount"])
        category = str(payload["category"]).strip()
        tx_date = datetime.strptime(str(payload["date"]), "%Y-%m-%d").date()
        notes = str(payload.get("notes", "")).strip()
    except (KeyError, TypeError, ValueError):
        return None
    if not description or len(description) > 180 or not category or len(category) > 80 or amount == 0 or len(notes) > 2000:
        return None
    return description, amount, category, tx_date, notes


@api.get("/health")
def health():
    return {"status": "ok", "service": "ledgerly-api", "version": "1.0.0"}


@api.post("/auth/register")
def register():
    payload = request.get_json() or {}
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    if not EMAIL_RE.match(email) or len(email) > 180 or len(password) < 8 or len(password) > 128:
        return {"error": "A valid email and an 8–128 character password are required."}, 400
    if User.query.filter_by(email=email).first():
        return {"error": "An account with that email already exists."}, 409
    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return {"accessToken": create_access_token(identity=str(user.id)), "user": {"email": user.email}}, 201


@api.post("/auth/login")
def login():
    payload = request.get_json() or {}
    email = str(payload.get("email", "")).strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(str(payload.get("password", ""))):
        return {"error": "Invalid email or password."}, 401
    return {"accessToken": create_access_token(identity=str(user.id)), "user": {"email": user.email}}


@api.get("/account")
@jwt_required()
def account():
    user = current_user()
    if not user:
        return {"error": "Account not found."}, 404
    return {
        "email": user.email,
        "createdAt": user.created_at.isoformat() if user.created_at else None,
        "transactionCount": Transaction.query.filter_by(user_id=user.id).count(),
        "budgetCount": Budget.query.filter_by(user_id=user.id).count(),
        "goalCount": Goal.query.filter_by(user_id=user.id).count(),
    }


@api.patch("/account/password")
@jwt_required()
def change_password():
    user = current_user()
    payload = request.get_json() or {}
    current_password = str(payload.get("currentPassword", ""))
    new_password = str(payload.get("newPassword", ""))
    if not user or not user.check_password(current_password):
        return {"error": "Current password is incorrect."}, 403
    if len(new_password) < 8 or len(new_password) > 128:
        return {"error": "New password must be 8–128 characters."}, 400
    if current_password == new_password:
        return {"error": "Choose a different password."}, 400
    user.set_password(new_password)
    db.session.commit()
    return {"updated": True}


@api.delete("/account")
@jwt_required()
def delete_account():
    user = current_user()
    payload = request.get_json(silent=True) or {}
    password = str(payload.get("password", ""))
    if not user or not user.check_password(password):
        return {"error": "Password confirmation is required."}, 403
    clear_financial_data(user.id)
    db.session.delete(user)
    db.session.commit()
    return {"deleted": True}


@api.get("/dashboard")
@jwt_required()
def dashboard():
    uid = current_user_id()
    transactions = Transaction.query.filter_by(user_id=uid).order_by(Transaction.date.desc(), Transaction.id.desc()).all()
    start, end = current_month_bounds()
    month_items = [t for t in transactions if start <= t.date <= end]
    month_income = sum(t.amount for t in month_items if t.amount > 0)
    month_expenses = abs(sum(t.amount for t in month_items if t.amount < 0))
    lifetime_balance = sum(t.amount for t in transactions)
    categories = {}
    for t in month_items:
        if t.amount < 0:
            categories[t.category] = categories.get(t.category, 0) + abs(t.amount)
    budgets = budget_payload(uid)
    goals = Goal.query.filter_by(user_id=uid).order_by(Goal.id.desc()).all()
    savings_rate = ((month_income - month_expenses) / month_income * 100) if month_income else 0
    return {
        "totalBalance": round(lifetime_balance, 2),
        "income": round(month_income, 2),
        "expenses": round(month_expenses, 2),
        "savingsRate": round(savings_rate, 2),
        "categories": sorted(({"category": k, "amount": round(v, 2)} for k, v in categories.items()), key=lambda x: x["amount"], reverse=True)[:8],
        "transactions": [t.to_dict() for t in transactions],
        "budgets": budgets,
        "goals": [serialize_goal(g) for g in goals],
        "monthlyTrend": monthly_trend(transactions),
    }


@api.route("/transactions", methods=["GET", "POST"])
@jwt_required()
def transactions():
    uid = current_user_id()
    if request.method == "GET":
        items = Transaction.query.filter_by(user_id=uid).order_by(Transaction.date.desc(), Transaction.id.desc()).all()
        return jsonify([item.to_dict() for item in items])
    parsed = parse_transaction_payload(request.get_json() or {})
    if not parsed:
        return {"error": "Description, non-zero amount, category, and YYYY-MM-DD date are required."}, 400
    description, amount, category, tx_date, notes = parsed
    item = Transaction(user_id=uid, description=description, amount=amount, category=category, date=tx_date, notes=notes)
    db.session.add(item)
    db.session.commit()
    return item.to_dict(), 201


@api.post("/transactions/import")
@jwt_required()
def import_transactions():
    uid = current_user_id()
    payload = request.get_json() or {}
    rows = payload.get("transactions")
    if not isinstance(rows, list) or not rows:
        return {"error": "Provide a non-empty transactions array."}, 400
    if len(rows) > MAX_IMPORT_ROWS:
        return {"error": f"Import is limited to {MAX_IMPORT_ROWS} rows at a time."}, 400
    parsed_rows = []
    errors = []
    for index, row in enumerate(rows, start=1):
        parsed = parse_transaction_payload(row if isinstance(row, dict) else {})
        if not parsed:
            errors.append(index)
        else:
            parsed_rows.append(parsed)
    if errors:
        preview = ", ".join(str(i) for i in errors[:10])
        suffix = "…" if len(errors) > 10 else ""
        return {"error": f"Invalid transaction data on row(s): {preview}{suffix}"}, 400
    for description, amount, category, tx_date, notes in parsed_rows:
        db.session.add(Transaction(user_id=uid, description=description, amount=amount, category=category, date=tx_date, notes=notes))
    db.session.commit()
    return {"imported": len(parsed_rows)}, 201


@api.patch("/transactions/<int:transaction_id>")
@jwt_required()
def update_transaction(transaction_id):
    item = Transaction.query.filter_by(id=transaction_id, user_id=current_user_id()).first_or_404()
    parsed = parse_transaction_payload(request.get_json() or {})
    if not parsed:
        return {"error": "Description, non-zero amount, category, and YYYY-MM-DD date are required."}, 400
    item.description, item.amount, item.category, item.date, item.notes = parsed
    db.session.commit()
    return item.to_dict()


@api.delete("/transactions/<int:transaction_id>")
@jwt_required()
def delete_transaction(transaction_id):
    item = Transaction.query.filter_by(id=transaction_id, user_id=current_user_id()).first_or_404()
    db.session.delete(item)
    db.session.commit()
    return {"deleted": transaction_id}


def budget_payload(uid):
    start, end = current_month_bounds()
    budgets = Budget.query.filter_by(user_id=uid).order_by(Budget.category.asc()).all()
    result = []
    for budget in budgets:
        spent = db.session.query(func.coalesce(func.sum(func.abs(Transaction.amount)), 0)).filter(
            Transaction.user_id == uid,
            Transaction.category == budget.category,
            Transaction.amount < 0,
            Transaction.date >= start,
            Transaction.date <= end,
        ).scalar()
        spent_value = float(spent or 0)
        result.append({
            "id": budget.id,
            "category": budget.category,
            "limit": budget.limit,
            "spent": round(spent_value, 2),
            "remaining": round(budget.limit - spent_value, 2),
        })
    return result


@api.route("/budgets", methods=["GET", "POST"])
@jwt_required()
def budgets():
    uid = current_user_id()
    if request.method == "GET":
        return jsonify(budget_payload(uid))
    payload = request.get_json() or {}
    try:
        category, limit = str(payload["category"]).strip(), float(payload["limit"])
    except (KeyError, TypeError, ValueError):
        return {"error": "Category and a positive limit are required."}, 400
    if not category or len(category) > 80 or limit <= 0:
        return {"error": "Category and a positive limit are required."}, 400
    existing = Budget.query.filter_by(user_id=uid, category=category).first()
    if existing:
        existing.limit = limit
        budget = existing
        status = 200
    else:
        budget = Budget(user_id=uid, category=category, limit=limit)
        db.session.add(budget)
        status = 201
    db.session.commit()
    return {"id": budget.id, "category": budget.category, "limit": budget.limit}, status


@api.patch("/budgets/<int:budget_id>")
@jwt_required()
def update_budget(budget_id):
    budget = Budget.query.filter_by(id=budget_id, user_id=current_user_id()).first_or_404()
    payload = request.get_json() or {}
    try:
        limit = float(payload["limit"])
    except (KeyError, TypeError, ValueError):
        return {"error": "A positive limit is required."}, 400
    if limit <= 0:
        return {"error": "A positive limit is required."}, 400
    budget.limit = limit
    db.session.commit()
    return {"id": budget.id, "category": budget.category, "limit": budget.limit}


@api.delete("/budgets/<int:budget_id>")
@jwt_required()
def delete_budget(budget_id):
    budget = Budget.query.filter_by(id=budget_id, user_id=current_user_id()).first_or_404()
    db.session.delete(budget)
    db.session.commit()
    return {"deleted": budget_id}


@api.route("/goals", methods=["GET", "POST"])
@jwt_required()
def goals():
    uid = current_user_id()
    if request.method == "GET":
        return jsonify([serialize_goal(g) for g in Goal.query.filter_by(user_id=uid).order_by(Goal.id.desc()).all()])
    payload = request.get_json() or {}
    try:
        name, target, saved = str(payload["name"]).strip(), float(payload["target"]), float(payload.get("saved", 0))
    except (KeyError, TypeError, ValueError):
        return {"error": "Name and a positive target are required."}, 400
    if not name or len(name) > 120 or target <= 0 or saved < 0:
        return {"error": "Invalid goal values."}, 400
    goal = Goal(user_id=uid, name=name, target=target, saved=saved)
    db.session.add(goal)
    db.session.commit()
    return serialize_goal(goal), 201


@api.patch("/goals/<int:goal_id>")
@jwt_required()
def update_goal(goal_id):
    goal = Goal.query.filter_by(id=goal_id, user_id=current_user_id()).first_or_404()
    payload = request.get_json() or {}
    try:
        name = str(payload.get("name", goal.name)).strip()
        target = float(payload.get("target", goal.target))
        saved = float(payload.get("saved", goal.saved))
    except (TypeError, ValueError):
        return {"error": "Invalid goal values."}, 400
    if not name or len(name) > 120 or target <= 0 or saved < 0:
        return {"error": "Invalid goal values."}, 400
    goal.name, goal.target, goal.saved = name, target, saved
    db.session.commit()
    return serialize_goal(goal)


@api.post("/goals/<int:goal_id>/contribute")
@jwt_required()
def contribute_goal(goal_id):
    goal = Goal.query.filter_by(id=goal_id, user_id=current_user_id()).first_or_404()
    payload = request.get_json() or {}
    try:
        amount = float(payload["amount"])
    except (KeyError, TypeError, ValueError):
        return {"error": "A positive contribution is required."}, 400
    if amount <= 0:
        return {"error": "A positive contribution is required."}, 400
    goal.saved += amount
    db.session.commit()
    return serialize_goal(goal)


@api.delete("/goals/<int:goal_id>")
@jwt_required()
def delete_goal(goal_id):
    goal = Goal.query.filter_by(id=goal_id, user_id=current_user_id()).first_or_404()
    db.session.delete(goal)
    db.session.commit()
    return {"deleted": goal_id}


@api.delete("/data")
@jwt_required()
def clear_data():
    uid = current_user_id()
    clear_financial_data(uid)
    db.session.commit()
    return {"cleared": True}


@api.post("/demo/seed")
@jwt_required()
def seed_demo():
    uid = current_user_id()
    if Transaction.query.filter_by(user_id=uid).first() or Budget.query.filter_by(user_id=uid).first() or Goal.query.filter_by(user_id=uid).first():
        return {"error": "Demo data can only be loaded into an empty account."}, 409
    seed_user(uid)
    db.session.commit()
    return {"seeded": True}, 201


@api.post("/demo/reset")
@jwt_required()
def reset_demo():
    uid = current_user_id()
    clear_financial_data(uid)
    seed_user(uid)
    db.session.commit()
    return {"seeded": True, "reset": True}
