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


@api.get("/health")
def health():
    return {"status": "ok", "service": "ledgerly-api"}


@api.post("/auth/register")
def register():
    payload = request.get_json() or {}
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    if not email or len(password) < 8:
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
    goals = Goal.query.filter_by(user_id=uid).all()
    savings_rate = ((income - expenses) / income * 100) if income else 0
    return {
        "totalBalance": income - expenses,
        "income": income,
        "expenses": expenses,
        "savingsRate": savings_rate,
        "categories": sorted(({"category": k, "amount": v} for k, v in categories.items()), key=lambda x: x["amount"], reverse=True)[:6],
        "transactions": [t.to_dict() for t in transactions[:12]],
        "budgets": budgets,
        "goals": [{"id": g.id, "name": g.name, "target": g.target, "saved": g.saved} for g in goals],
    }


@api.route("/transactions", methods=["GET", "POST"])
@jwt_required()
def transactions():
    uid = current_user_id()
    if request.method == "GET":
        items = Transaction.query.filter_by(user_id=uid).order_by(Transaction.date.desc()).all()
        return jsonify([item.to_dict() for item in items])
    payload = request.get_json() or {}
    try:
        item = Transaction(user_id=uid, description=str(payload["description"]).strip(), amount=float(payload["amount"]), category=str(payload["category"]).strip(), date=datetime.strptime(payload["date"], "%Y-%m-%d").date())
    except (KeyError, TypeError, ValueError):
        return {"error": "description, amount, category, and YYYY-MM-DD date are required."}, 400
    if not item.description or not item.category or item.amount == 0:
        return {"error": "Description/category cannot be empty and amount cannot be zero."}, 400
    db.session.add(item)
    db.session.commit()
    return item.to_dict(), 201


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
    budgets = Budget.query.filter_by(user_id=uid).all()
    result = []
    for budget in budgets:
        spent = db.session.query(func.coalesce(func.sum(func.abs(Transaction.amount)), 0)).filter(Transaction.user_id == uid, Transaction.category == budget.category, Transaction.amount < 0, Transaction.date >= start, Transaction.date <= end).scalar()
        result.append({"id": budget.id, "category": budget.category, "limit": budget.limit, "spent": float(spent or 0)})
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
        return {"error": "category and positive limit are required."}, 400
    if not category or limit <= 0:
        return {"error": "category and positive limit are required."}, 400
    existing = Budget.query.filter_by(user_id=uid, category=category).first()
    if existing:
        existing.limit = limit
        budget = existing
    else:
        budget = Budget(user_id=uid, category=category, limit=limit)
        db.session.add(budget)
    db.session.commit()
    return {"id": budget.id, "category": budget.category, "limit": budget.limit}, 201


@api.route("/goals", methods=["GET", "POST"])
@jwt_required()
def goals():
    uid = current_user_id()
    if request.method == "GET":
        return jsonify([{"id": g.id, "name": g.name, "target": g.target, "saved": g.saved} for g in Goal.query.filter_by(user_id=uid).all()])
    payload = request.get_json() or {}
    try:
        name, target, saved = str(payload["name"]).strip(), float(payload["target"]), float(payload.get("saved", 0))
    except (KeyError, TypeError, ValueError):
        return {"error": "name and a positive target are required."}, 400
    if not name or target <= 0 or saved < 0:
        return {"error": "Invalid goal values."}, 400
    goal = Goal(user_id=uid, name=name, target=target, saved=saved)
    db.session.add(goal)
    db.session.commit()
    return {"id": goal.id, "name": goal.name, "target": goal.target, "saved": goal.saved}, 201


@api.post("/demo/seed")
@jwt_required()
def seed_demo():
    uid = current_user_id()
    if Transaction.query.filter_by(user_id=uid).first():
        return {"error": "Demo data can only be loaded into an empty account."}, 409
    today = date.today()
    tx = [
        ("Paycheck", 3200, "Income"), ("Freelance project", 1450, "Income"), ("Rent", -1150, "Housing"),
        ("Groceries", -286.42, "Food & Dining"), ("Electric bill", -142.18, "Utilities"), ("Fuel", -96.70, "Transport"),
        ("Coffee", -18.64, "Food & Dining"), ("Internet", -79.99, "Utilities"), ("Gym", -34.99, "Lifestyle")
    ]
    for description, amount, category in tx:
        db.session.add(Transaction(user_id=uid, description=description, amount=amount, category=category, date=today))
    for category, limit in [("Food & Dining", 500), ("Transport", 250), ("Lifestyle", 200), ("Utilities", 350)]:
        db.session.add(Budget(user_id=uid, category=category, limit=limit))
    db.session.add_all([Goal(user_id=uid, name="Emergency fund", target=6000, saved=2450), Goal(user_id=uid, name="Weekend trip", target=1200, saved=480)])
    db.session.commit()
    return {"seeded": True}, 201
