from calendar import monthrange
from datetime import date, datetime
from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from sqlalchemy import func
from .extensions import db
from .models import Budget, Goal, Transaction, User

api = Blueprint("api", __name__, url_prefix="/api")


def current_user_id():
    return int(get_jwt_identity())


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
    months = month_keys(6)
    result = []
    for year, month in months:
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


@api.get("/health")
def health():
    return {"status": "ok", "service": "ledgerly-api"}


@api.post("/auth/register")
def register():
    payload = request.get_json() or {}
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    if "@" not in email or len(password) < 8:
        return {"error": "A valid email and an 8+ character password are required."}, 400
    if User.query.filter_by(email=email).first():
        return {"error": "An account with that email already exists."}, 409
    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return {"accessToken": create_access_token(identity=str(user.id))}, 201


@api.post("/auth/login")
def login():
    payload = request.get_json() or {}
    email = str(payload.get("email", "")).strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(str(payload.get("password", ""))):
        return {"error": "Invalid email or password."}, 401
    return {"accessToken": create_access_token(identity=str(user.id))}


@api.get("/dashboard")
@jwt_required()
def dashboard():
    uid = current_user_id()
    transactions = Transaction.query.filter_by(user_id=uid).order_by(Transaction.date.desc(), Transaction.id.desc()).all()
    income = sum(t.amount for t in transactions if t.amount > 0)
    expenses = abs(sum(t.amount for t in transactions if t.amount < 0))
    categories = {}
    for t in transactions:
        if t.amount < 0:
            categories[t.category] = categories.get(t.category, 0) + abs(t.amount)
    budgets = budget_payload(uid)
    goals = Goal.query.filter_by(user_id=uid).order_by(Goal.id.desc()).all()
    savings_rate = ((income - expenses) / income * 100) if income else 0
    return {
        "totalBalance": round(income - expenses, 2),
        "income": round(income, 2),
        "expenses": round(expenses, 2),
        "savingsRate": round(savings_rate, 2),
        "categories": sorted(({"category": k, "amount": round(v, 2)} for k, v in categories.items()), key=lambda x: x["amount"], reverse=True)[:8],
        "transactions": [t.to_dict() for t in transactions],
        "budgets": budgets,
        "goals": [serialize_goal(g) for g in goals],
        "monthlyTrend": monthly_trend(transactions),
    }


def parse_transaction_payload(payload):
    try:
        description = str(payload["description"]).strip()
        amount = float(payload["amount"])
        category = str(payload["category"]).strip()
        tx_date = datetime.strptime(payload["date"], "%Y-%m-%d").date()
        notes = str(payload.get("notes", "")).strip()
    except (KeyError, TypeError, ValueError):
        return None
    if not description or not category or amount == 0:
        return None
    return description, amount, category, tx_date, notes


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
    today = date.today()
    start = date(today.year, today.month, 1)
    end = date(today.year, today.month, monthrange(today.year, today.month)[1])
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
    if not category or limit <= 0:
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
    if not name or target <= 0 or saved < 0:
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
    if not name or target <= 0 or saved < 0:
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


@api.post("/demo/seed")
@jwt_required()
def seed_demo():
    uid = current_user_id()
    if Transaction.query.filter_by(user_id=uid).first():
        return {"error": "Demo data can only be loaded into an empty account."}, 409

    months = month_keys(6)
    for index, (year, month) in enumerate(months):
        day = min(18, monthrange(year, month)[1])
        tx_date = date(year, month, day)
        db.session.add(Transaction(user_id=uid, description="Paycheck", amount=3200 + index * 45, category="Income", date=tx_date))
        db.session.add(Transaction(user_id=uid, description="Rent", amount=-1150, category="Housing", date=tx_date))
        db.session.add(Transaction(user_id=uid, description="Groceries", amount=-(245 + index * 7.5), category="Food & Dining", date=tx_date))
        db.session.add(Transaction(user_id=uid, description="Utilities", amount=-(185 + index * 4), category="Utilities", date=tx_date))

    today = date.today()
    extras = [
        ("Freelance project", 1450, "Income"),
        ("Fuel", -96.70, "Transport"),
        ("Coffee", -18.64, "Food & Dining"),
        ("Internet", -79.99, "Utilities"),
        ("Gym", -34.99, "Lifestyle"),
    ]
    for description, amount, category in extras:
        db.session.add(Transaction(user_id=uid, description=description, amount=amount, category=category, date=today))

    for category, limit in [("Food & Dining", 500), ("Transport", 250), ("Lifestyle", 200), ("Utilities", 350)]:
        db.session.add(Budget(user_id=uid, category=category, limit=limit))
    db.session.add_all([
        Goal(user_id=uid, name="Emergency fund", target=6000, saved=2450),
        Goal(user_id=uid, name="Weekend trip", target=1200, saved=480),
    ])
    db.session.commit()
    return {"seeded": True}, 201
