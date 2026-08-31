from calendar import monthrange
from datetime import UTC, date, datetime
from uuid import uuid4

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from .extensions import db
from .firebase_auth import firebase_required, get_jwt_identity
from .models import Budget, FinancialAccount, Goal, Transaction, User

api = Blueprint("api", __name__, url_prefix="/api")
MAX_IMPORT_ROWS = 1000
ACCOUNT_TYPES = {"checking", "savings", "cash", "credit", "loan", "investment", "other"}
TRANSACTION_TYPES = {"income", "expense", "transfer"}


def current_user_id():
    return int(get_jwt_identity())


def current_user():
    return db.session.get(User, current_user_id())


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


def current_month_bounds():
    today = date.today()
    return date(today.year, today.month, 1), date(today.year, today.month, monthrange(today.year, today.month)[1])


def normalize_transaction_type(value, amount):
    raw = str(value or "").strip().lower()
    if raw in TRANSACTION_TYPES:
        return raw
    return "income" if amount > 0 else "expense"


def account_map(uid):
    return {account.id: account for account in FinancialAccount.query.filter_by(user_id=uid).all()}


def account_balance(account):
    movement = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.user_id == account.user_id,
        Transaction.account_id == account.id,
    ).scalar()
    return round(float(account.opening_balance or 0) + float(movement or 0), 2)


def serialize_account(account):
    return {
        "id": account.id,
        "name": account.name,
        "type": account.account_type,
        "institution": account.institution or "",
        "openingBalance": round(float(account.opening_balance or 0), 2),
        "currentBalance": account_balance(account),
        "description": account.description or "",
        "includeInTotals": bool(account.include_in_totals),
        "archived": bool(account.archived),
        "transactionCount": Transaction.query.filter_by(user_id=account.user_id, account_id=account.id).count(),
        "createdAt": account.created_at.isoformat() if account.created_at else None,
    }


def serialize_transaction(transaction, accounts=None):
    account = (accounts or {}).get(transaction.account_id) if transaction.account_id else None
    return transaction.to_dict(account.name if account else None)


def serialize_goal(goal):
    target = float(goal.target or 0)
    saved = float(goal.saved or 0)
    return {
        "id": goal.id,
        "name": goal.name,
        "target": target,
        "saved": saved,
        "targetDate": goal.target_date.isoformat() if goal.target_date else None,
        "notes": goal.notes or "",
        "amountRemaining": round(max(target - saved, 0), 2),
        "percentComplete": round(min((saved / target * 100) if target else 0, 100), 2),
    }


def monthly_trend(transactions):
    result = []
    for year, month in month_keys(6):
        items = [item for item in transactions if item.date.year == year and item.date.month == month and item.transaction_type != "transfer"]
        income = sum(item.amount for item in items if item.transaction_type == "income" or (not item.transaction_type and item.amount > 0))
        expenses = abs(sum(item.amount for item in items if item.transaction_type == "expense" or (not item.transaction_type and item.amount < 0)))
        result.append({
            "month": date(year, month, 1).strftime("%b"),
            "income": round(income, 2),
            "expenses": round(expenses, 2),
            "net": round(income - expenses, 2),
        })
    return result


def clear_financial_data(uid):
    Transaction.query.filter_by(user_id=uid).delete()
    Budget.query.filter_by(user_id=uid).delete()
    Goal.query.filter_by(user_id=uid).delete()
    FinancialAccount.query.filter_by(user_id=uid).delete()


def owned_account(uid, account_id):
    if account_id in (None, "", 0, "0"):
        return None
    try:
        normalized = int(account_id)
    except (TypeError, ValueError):
        return False
    return FinancialAccount.query.filter_by(id=normalized, user_id=uid).first() or False


def parse_account_payload(payload, existing=None):
    try:
        name = str(payload.get("name", existing.name if existing else "")).strip()
        account_type = str(payload.get("type", existing.account_type if existing else "checking")).strip().lower()
        institution = str(payload.get("institution", existing.institution if existing else "") or "").strip()
        opening_balance = float(payload.get("openingBalance", existing.opening_balance if existing else 0))
        description = str(payload.get("description", existing.description if existing else "") or "").strip()
        include_in_totals = payload.get("includeInTotals", existing.include_in_totals if existing else True)
        archived = payload.get("archived", existing.archived if existing else False)
        if not isinstance(include_in_totals, bool) or not isinstance(archived, bool):
            return None
    except (TypeError, ValueError):
        return None
    if not name or len(name) > 120 or account_type not in ACCOUNT_TYPES or len(institution) > 120 or len(description) > 500:
        return None
    return name, account_type, institution, opening_balance, description, include_in_totals, archived


def parse_transaction_payload(payload, uid):
    try:
        description = str(payload["description"]).strip()
        amount = float(payload["amount"])
        category = str(payload["category"]).strip()
        tx_date = datetime.strptime(str(payload["date"]), "%Y-%m-%d").date()
        notes = str(payload.get("notes", "")).strip()
        subcategory = str(payload.get("subcategory", "") or "").strip()
    except (KeyError, TypeError, ValueError):
        return None, "Description, non-zero amount, category, and YYYY-MM-DD date are required."

    if not description or len(description) > 80 or not category or len(category) > 80 or amount == 0 or len(notes) > 500 or len(subcategory) > 80:
        return None, "Description, non-zero amount, category, and YYYY-MM-DD date are required."

    transaction_type = normalize_transaction_type(payload.get("transactionType"), amount)
    if transaction_type == "transfer":
        return None, "Create transfers with the transfer workflow so both accounts stay balanced."
    amount = abs(amount) if transaction_type == "income" else -abs(amount)

    account = owned_account(uid, payload.get("accountId"))
    if account is False:
        return None, "The selected account was not found."
    if account and account.archived:
        return None, "Archived accounts cannot receive new transactions."

    raw_tags = payload.get("tags", [])
    if isinstance(raw_tags, list):
        tags = ",".join(str(tag).strip() for tag in raw_tags if str(tag).strip())
    else:
        tags = str(raw_tags or "").strip()
    if len(tags) > 500:
        return None, "Tags are too long."

    return {
        "description": description,
        "amount": amount,
        "transaction_type": transaction_type,
        "account_id": account.id if account else None,
        "category": category,
        "subcategory": subcategory or None,
        "tags": tags or None,
        "date": tx_date,
        "notes": notes,
    }, None


def budget_payload(uid):
    start, end = current_month_bounds()
    budgets = Budget.query.filter_by(user_id=uid).order_by(Budget.category.asc()).all()
    result = []
    for budget in budgets:
        spent = db.session.query(func.coalesce(func.sum(func.abs(Transaction.amount)), 0)).filter(
            Transaction.user_id == uid,
            Transaction.category == budget.category,
            Transaction.transaction_type == "expense",
            Transaction.date >= start,
            Transaction.date <= end,
        ).scalar()
        spent_value = float(spent or 0)
        percent = (spent_value / budget.limit * 100) if budget.limit else 0
        status = "over" if percent >= 100 else "approaching" if percent >= 80 else "healthy"
        result.append({
            "id": budget.id,
            "category": budget.category,
            "limit": budget.limit,
            "spent": round(spent_value, 2),
            "remaining": round(budget.limit - spent_value, 2),
            "percentUsed": round(percent, 2),
            "status": status,
        })
    return result


def build_insights(month_income, month_expenses, categories, budgets, goals):
    insights = []
    if categories:
        top = max(categories.items(), key=lambda item: item[1])
        insights.append(f"{top[0]} is your largest spending category this month at ${top[1]:,.2f}.")
    approaching = [item for item in budgets if item["status"] == "approaching"]
    over = [item for item in budgets if item["status"] == "over"]
    if over:
        insights.append(f"{len(over)} budget{'s are' if len(over) != 1 else ' is'} over the monthly limit.")
    elif approaching:
        insights.append(f"{len(approaching)} budget{'s are' if len(approaching) != 1 else ' is'} above 80% used.")
    elif budgets:
        insights.append("All active budgets are currently within their monthly limits.")
    if month_income:
        net = month_income - month_expenses
        insights.append(f"Your net cash flow is {'positive' if net >= 0 else 'negative'} by ${abs(net):,.2f} this month.")
    if goals:
        nearest = min(goals, key=lambda goal: max(goal.target - goal.saved, 0))
        remaining = max(nearest.target - nearest.saved, 0)
        insights.append(f"You are ${remaining:,.2f} away from your {nearest.name} goal." if remaining else f"Your {nearest.name} goal is fully funded.")
    return insights[:4]


def seed_user(uid):
    checking = FinancialAccount(user_id=uid, name="Everyday Checking", account_type="checking", institution="Northstar Community Bank", opening_balance=450)
    savings = FinancialAccount(user_id=uid, name="Emergency Savings", account_type="savings", institution="Northstar Community Bank", opening_balance=1200)
    db.session.add_all([checking, savings])
    db.session.flush()

    for index, (year, month) in enumerate(month_keys(6)):
        day = min(18, monthrange(year, month)[1])
        tx_date = date(year, month, day)
        entries = [
            ("Paycheck", 3200 + index * 45, "income", "Income", "Primary income"),
            ("Rent", -1150, "expense", "Housing", "Monthly rent"),
            ("Groceries", -(245 + index * 7.5), "expense", "Groceries", "Household groceries"),
            ("Utilities", -(185 + index * 4), "expense", "Utilities", "Electric and water"),
        ]
        for description, amount, transaction_type, category, notes in entries:
            db.session.add(Transaction(user_id=uid, account_id=checking.id, description=description, amount=amount, transaction_type=transaction_type, category=category, date=tx_date, notes=notes))

    current = date.today()
    extras = [
        ("Freelance project", 1450, "income", "Income", "One-off client work"),
        ("Fuel", -96.70, "expense", "Fuel", "Vehicle fuel"),
        ("Coffee shop", -18.64, "expense", "Dining", "Coffee with a friend"),
        ("Home internet", -79.99, "expense", "Utilities", "Monthly internet"),
        ("Streaming bundle", -34.99, "expense", "Subscriptions", "Monthly services"),
    ]
    for description, amount, transaction_type, category, notes in extras:
        db.session.add(Transaction(user_id=uid, account_id=checking.id, description=description, amount=amount, transaction_type=transaction_type, category=category, date=current, notes=notes))

    group = uuid4().hex
    db.session.add_all([
        Transaction(user_id=uid, account_id=checking.id, description="Savings transfer", amount=-250, transaction_type="transfer", category="Transfer", date=current, notes="Monthly savings", transfer_group=group),
        Transaction(user_id=uid, account_id=savings.id, description="Savings transfer", amount=250, transaction_type="transfer", category="Transfer", date=current, notes="Monthly savings", transfer_group=group),
    ])
    for category, limit in [("Groceries", 500), ("Fuel", 250), ("Subscriptions", 150), ("Utilities", 350)]:
        db.session.add(Budget(user_id=uid, category=category, limit=limit))
    db.session.add_all([
        Goal(user_id=uid, name="Emergency fund", target=6000, saved=2450, notes="Six months of essential expenses"),
        Goal(user_id=uid, name="Weekend trip", target=1200, saved=480, notes="Travel and lodging"),
    ])


@api.get("/health")
def health():
    return {"status": "ok", "service": "ledgerly-api", "version": "1.2.0", "auth": "firebase"}


@api.get("/account")
@firebase_required()
def account():
    user = current_user()
    if not user:
        return {"error": "Account not found."}, 404
    return {
        "email": user.email,
        "emailVerified": user.email_verified,
        "createdAt": user.created_at.isoformat() if user.created_at else None,
        "transactionCount": Transaction.query.filter_by(user_id=user.id).count(),
        "budgetCount": Budget.query.filter_by(user_id=user.id).count(),
        "goalCount": Goal.query.filter_by(user_id=user.id).count(),
        "financialAccountCount": FinancialAccount.query.filter_by(user_id=user.id, archived=False).count(),
    }


@api.delete("/account")
@firebase_required()
def delete_account():
    user = current_user()
    if not user:
        return {"error": "Account not found."}, 404
    clear_financial_data(user.id)
    db.session.delete(user)
    db.session.commit()
    return {"deleted": True}


@api.route("/accounts", methods=["GET", "POST"])
@firebase_required()
def accounts():
    uid = current_user_id()
    if request.method == "GET":
        items = FinancialAccount.query.filter_by(user_id=uid).order_by(FinancialAccount.archived.asc(), FinancialAccount.name.asc()).all()
        return jsonify([serialize_account(item) for item in items])
    parsed = parse_account_payload(request.get_json() or {})
    if not parsed:
        return {"error": "Name, supported account type, and valid account values are required."}, 400
    name, account_type, institution, opening_balance, description, include_in_totals, archived = parsed
    item = FinancialAccount(user_id=uid, name=name, account_type=account_type, institution=institution, opening_balance=opening_balance, description=description, include_in_totals=include_in_totals, archived=archived)
    db.session.add(item)
    db.session.commit()
    return serialize_account(item), 201


@api.patch("/accounts/<int:account_id>")
@firebase_required()
def update_account(account_id):
    item = FinancialAccount.query.filter_by(id=account_id, user_id=current_user_id()).first_or_404()
    parsed = parse_account_payload(request.get_json() or {}, item)
    if not parsed:
        return {"error": "Invalid account values."}, 400
    item.name, item.account_type, item.institution, item.opening_balance, item.description, item.include_in_totals, item.archived = parsed
    db.session.commit()
    return serialize_account(item)


@api.delete("/accounts/<int:account_id>")
@firebase_required()
def delete_financial_account(account_id):
    uid = current_user_id()
    item = FinancialAccount.query.filter_by(id=account_id, user_id=uid).first_or_404()
    transaction_count = Transaction.query.filter_by(user_id=uid, account_id=item.id).count()
    detach = str(request.args.get("detach", "false")).lower() == "true"
    if transaction_count and not detach:
        return {"error": "This account has transactions. Archive it, or explicitly detach its transactions before deleting it.", "transactionCount": transaction_count}, 409
    if transaction_count:
        Transaction.query.filter_by(user_id=uid, account_id=item.id).update({"account_id": None})
    db.session.delete(item)
    db.session.commit()
    return {"deleted": account_id, "detachedTransactions": transaction_count}


@api.get("/dashboard")
@firebase_required()
def dashboard():
    uid = current_user_id()
    accounts_by_id = account_map(uid)
    accounts_serialized = [serialize_account(item) for item in sorted(accounts_by_id.values(), key=lambda item: (item.archived, item.name.lower()))]
    transactions = Transaction.query.filter_by(user_id=uid).order_by(Transaction.date.desc(), Transaction.id.desc()).all()
    start, end = current_month_bounds()
    month_items = [item for item in transactions if start <= item.date <= end and item.transaction_type != "transfer"]
    month_income = sum(item.amount for item in month_items if item.transaction_type == "income" or (not item.transaction_type and item.amount > 0))
    month_expenses = abs(sum(item.amount for item in month_items if item.transaction_type == "expense" or (not item.transaction_type and item.amount < 0)))

    if accounts_serialized:
        tracked_balance = sum(item["currentBalance"] for item in accounts_serialized if item["includeInTotals"] and not item["archived"])
        unassigned_balance = sum(item.amount for item in transactions if item.account_id is None)
        total_balance = tracked_balance + unassigned_balance
    else:
        total_balance = sum(item.amount for item in transactions)

    categories = {}
    for item in month_items:
        if item.transaction_type == "expense" or (not item.transaction_type and item.amount < 0):
            categories[item.category] = categories.get(item.category, 0) + abs(item.amount)

    budgets = budget_payload(uid)
    goals = Goal.query.filter_by(user_id=uid).order_by(Goal.id.desc()).all()
    budget_categories = {item["category"] for item in budgets}
    unbudgeted_spending = sum(amount for category, amount in categories.items() if category not in budget_categories)
    budget_remaining = sum(item["remaining"] for item in budgets)
    net_cash_flow = month_income - month_expenses
    savings_rate = (net_cash_flow / month_income * 100) if month_income else 0
    actual_expense_categories = sorted(({"category": key, "amount": round(value, 2)} for key, value in categories.items()), key=lambda item: item["amount"], reverse=True)[:12]
    savings_contribution = sum(
        item.amount for item in transactions
        if start <= item.date <= end and item.transaction_type == "transfer" and item.amount > 0 and item.account_id in accounts_by_id and accounts_by_id[item.account_id].account_type == "savings"
    )
    days_remaining = max((end - date.today()).days + 1, 0)

    return {
        "totalBalance": round(total_balance, 2),
        "availableBalance": round(total_balance, 2),
        "income": round(month_income, 2),
        "expenses": round(month_expenses, 2),
        "netCashFlow": round(net_cash_flow, 2),
        "savingsRate": round(savings_rate, 2),
        "budgetRemaining": round(budget_remaining, 2),
        "unbudgetedSpending": round(unbudgeted_spending, 2),
        "categories": actual_expense_categories,
        "accounts": accounts_serialized,
        "transactions": [serialize_transaction(item, accounts_by_id) for item in transactions],
        "budgets": budgets,
        "goals": [serialize_goal(goal) for goal in goals],
        "monthlyTrend": monthly_trend(transactions),
        "monthlyPlan": {
            "expectedIncome": round(month_income, 2),
            "actualIncome": round(month_income, 2),
            "budgetedExpenses": round(sum(item["limit"] for item in budgets), 2),
            "actualExpenses": round(month_expenses, 2),
            "amountRemaining": round(net_cash_flow, 2),
            "unbudgetedSpending": round(unbudgeted_spending, 2),
            "savingsContribution": round(savings_contribution, 2),
            "netResult": round(net_cash_flow, 2),
            "daysRemaining": days_remaining,
        },
        "insights": build_insights(month_income, month_expenses, categories, budgets, goals),
    }


@api.route("/transactions", methods=["GET", "POST"])
@firebase_required()
def transactions():
    uid = current_user_id()
    if request.method == "GET":
        accounts_by_id = account_map(uid)
        items = Transaction.query.filter_by(user_id=uid).order_by(Transaction.date.desc(), Transaction.id.desc()).all()
        return jsonify([serialize_transaction(item, accounts_by_id) for item in items])
    parsed, error = parse_transaction_payload(request.get_json() or {}, uid)
    if not parsed:
        return {"error": error}, 400
    item = Transaction(user_id=uid, **parsed)
    db.session.add(item)
    db.session.commit()
    return serialize_transaction(item, account_map(uid)), 201


@api.post("/transfers")
@firebase_required()
def create_transfer():
    uid = current_user_id()
    payload = request.get_json() or {}
    try:
        from_id = int(payload["fromAccountId"])
        to_id = int(payload["toAccountId"])
        amount = abs(float(payload["amount"]))
        tx_date = datetime.strptime(str(payload["date"]), "%Y-%m-%d").date()
        description = str(payload.get("description") or "Transfer").strip()
        notes = str(payload.get("notes") or "").strip()
    except (KeyError, TypeError, ValueError):
        return {"error": "From account, to account, positive amount, and YYYY-MM-DD date are required."}, 400
    if from_id == to_id or amount <= 0 or not description or len(description) > 80 or len(notes) > 500:
        return {"error": "Choose two different accounts and a positive transfer amount."}, 400
    source = FinancialAccount.query.filter_by(id=from_id, user_id=uid, archived=False).first()
    destination = FinancialAccount.query.filter_by(id=to_id, user_id=uid, archived=False).first()
    if not source or not destination:
        return {"error": "Both transfer accounts must belong to you and be active."}, 400

    group = uuid4().hex
    outgoing = Transaction(user_id=uid, account_id=source.id, description=description, amount=-amount, transaction_type="transfer", category="Transfer", date=tx_date, notes=notes, transfer_group=group)
    incoming = Transaction(user_id=uid, account_id=destination.id, description=description, amount=amount, transaction_type="transfer", category="Transfer", date=tx_date, notes=notes, transfer_group=group)
    db.session.add_all([outgoing, incoming])
    db.session.commit()
    accounts_by_id = {source.id: source, destination.id: destination}
    return {"transferGroup": group, "transactions": [serialize_transaction(outgoing, accounts_by_id), serialize_transaction(incoming, accounts_by_id)]}, 201


@api.post("/transactions/import")
@firebase_required()
def import_transactions():
    uid = current_user_id()
    payload = request.get_json() or {}
    rows = payload.get("transactions")
    allow_partial = payload.get("allowPartial", False) is True
    default_account = owned_account(uid, payload.get("defaultAccountId"))
    if default_account is False:
        return {"error": "The selected import account was not found."}, 400
    if not isinstance(rows, list) or not rows:
        return {"error": "Provide a non-empty transactions array."}, 400
    if len(rows) > MAX_IMPORT_ROWS:
        return {"error": f"Import is limited to {MAX_IMPORT_ROWS} rows at a time."}, 400

    existing = Transaction.query.filter_by(user_id=uid).all()
    fingerprints = {(item.description.strip().lower(), round(float(item.amount), 2), item.category.strip().lower(), item.date.isoformat(), item.account_id) for item in existing}
    parsed_rows, invalid_rows, duplicate_rows = [], [], []
    for index, row in enumerate(rows, start=1):
        source = dict(row) if isinstance(row, dict) else {}
        if source.get("accountId") in (None, "") and default_account:
            source["accountId"] = default_account.id
        parsed, _error = parse_transaction_payload(source, uid)
        if not parsed:
            invalid_rows.append(index)
            continue
        fingerprint = (parsed["description"].lower(), round(float(parsed["amount"]), 2), parsed["category"].lower(), parsed["date"].isoformat(), parsed["account_id"])
        if fingerprint in fingerprints:
            duplicate_rows.append(index)
            continue
        fingerprints.add(fingerprint)
        parsed_rows.append(parsed)

    if invalid_rows and not allow_partial:
        preview = ", ".join(str(index) for index in invalid_rows[:10])
        suffix = "…" if len(invalid_rows) > 10 else ""
        return {"error": f"Invalid transaction data on row(s): {preview}{suffix}", "invalidRows": invalid_rows}, 400

    for parsed in parsed_rows:
        db.session.add(Transaction(user_id=uid, **parsed))
    db.session.commit()
    return {"imported": len(parsed_rows), "invalidRows": invalid_rows, "skippedDuplicates": duplicate_rows, "duplicateRows": duplicate_rows}, 201


@api.patch("/transactions/<int:transaction_id>")
@firebase_required()
def update_transaction(transaction_id):
    uid = current_user_id()
    item = Transaction.query.filter_by(id=transaction_id, user_id=uid).first_or_404()
    if item.transaction_type == "transfer" or item.transfer_group:
        return {"error": "Transfers are paired entries. Delete and recreate the transfer instead of editing one side."}, 409
    parsed, error = parse_transaction_payload(request.get_json() or {}, uid)
    if not parsed:
        return {"error": error}, 400
    for key, value in parsed.items():
        setattr(item, key, value)
    db.session.commit()
    return serialize_transaction(item, account_map(uid))


@api.delete("/transactions/<int:transaction_id>")
@firebase_required()
def delete_transaction(transaction_id):
    uid = current_user_id()
    item = Transaction.query.filter_by(id=transaction_id, user_id=uid).first_or_404()
    if item.transfer_group:
        group = item.transfer_group
        deleted = Transaction.query.filter_by(user_id=uid, transfer_group=group).delete()
        db.session.commit()
        return {"deleted": transaction_id, "deletedTransferEntries": deleted, "transferGroup": group}
    db.session.delete(item)
    db.session.commit()
    return {"deleted": transaction_id}


@api.route("/budgets", methods=["GET", "POST"])
@firebase_required()
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
        existing.limit, budget, status = limit, existing, 200
    else:
        budget, status = Budget(user_id=uid, category=category, limit=limit), 201
        db.session.add(budget)
    db.session.commit()
    return next(item for item in budget_payload(uid) if item["id"] == budget.id), status


@api.patch("/budgets/<int:budget_id>")
@firebase_required()
def update_budget(budget_id):
    uid = current_user_id()
    budget = Budget.query.filter_by(id=budget_id, user_id=uid).first_or_404()
    payload = request.get_json() or {}
    try:
        limit = float(payload["limit"])
    except (KeyError, TypeError, ValueError):
        return {"error": "A positive limit is required."}, 400
    if limit <= 0:
        return {"error": "A positive limit is required."}, 400
    budget.limit = limit
    db.session.commit()
    return next(item for item in budget_payload(uid) if item["id"] == budget.id)


@api.delete("/budgets/<int:budget_id>")
@firebase_required()
def delete_budget(budget_id):
    budget = Budget.query.filter_by(id=budget_id, user_id=current_user_id()).first_or_404()
    db.session.delete(budget)
    db.session.commit()
    return {"deleted": budget_id}


@api.route("/goals", methods=["GET", "POST"])
@firebase_required()
def goals():
    uid = current_user_id()
    if request.method == "GET":
        return jsonify([serialize_goal(goal) for goal in Goal.query.filter_by(user_id=uid).order_by(Goal.id.desc()).all()])
    payload = request.get_json() or {}
    try:
        name = str(payload["name"]).strip()
        target = float(payload["target"])
        saved = float(payload.get("saved", 0))
        notes = str(payload.get("notes", "") or "").strip()
        target_date = datetime.strptime(str(payload["targetDate"]), "%Y-%m-%d").date() if payload.get("targetDate") else None
    except (KeyError, TypeError, ValueError):
        return {"error": "Name and a positive target are required."}, 400
    if not name or len(name) > 120 or target <= 0 or saved < 0 or len(notes) > 2000:
        return {"error": "Invalid goal values."}, 400
    goal = Goal(user_id=uid, name=name, target=target, saved=saved, target_date=target_date, notes=notes)
    db.session.add(goal)
    db.session.commit()
    return serialize_goal(goal), 201


@api.patch("/goals/<int:goal_id>")
@firebase_required()
def update_goal(goal_id):
    goal = Goal.query.filter_by(id=goal_id, user_id=current_user_id()).first_or_404()
    payload = request.get_json() or {}
    try:
        name = str(payload.get("name", goal.name)).strip()
        target = float(payload.get("target", goal.target))
        saved = float(payload.get("saved", goal.saved))
        notes = str(payload.get("notes", goal.notes or "") or "").strip()
        target_date = datetime.strptime(str(payload["targetDate"]), "%Y-%m-%d").date() if payload.get("targetDate") else (None if "targetDate" in payload else goal.target_date)
    except (TypeError, ValueError):
        return {"error": "Invalid goal values."}, 400
    if not name or len(name) > 120 or target <= 0 or saved < 0 or len(notes) > 2000:
        return {"error": "Invalid goal values."}, 400
    goal.name, goal.target, goal.saved, goal.target_date, goal.notes = name, target, saved, target_date, notes
    db.session.commit()
    return serialize_goal(goal)


@api.post("/goals/<int:goal_id>/contribute")
@firebase_required()
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
@firebase_required()
def delete_goal(goal_id):
    goal = Goal.query.filter_by(id=goal_id, user_id=current_user_id()).first_or_404()
    db.session.delete(goal)
    db.session.commit()
    return {"deleted": goal_id}


@api.get("/export")
@firebase_required()
def export_data():
    uid = current_user_id()
    accounts_by_id = account_map(uid)
    return {
        "exportedAt": datetime.now(UTC).isoformat(),
        "accounts": [serialize_account(item) for item in accounts_by_id.values()],
        "transactions": [serialize_transaction(item, accounts_by_id) for item in Transaction.query.filter_by(user_id=uid).order_by(Transaction.date.desc(), Transaction.id.desc()).all()],
        "budgets": budget_payload(uid),
        "goals": [serialize_goal(goal) for goal in Goal.query.filter_by(user_id=uid).order_by(Goal.id.desc()).all()],
    }


@api.delete("/data")
@firebase_required()
def clear_data():
    uid = current_user_id()
    clear_financial_data(uid)
    db.session.commit()
    return {"cleared": True}


@api.post("/demo/seed")
@firebase_required()
def seed_demo():
    uid = current_user_id()
    if Transaction.query.filter_by(user_id=uid).first() or Budget.query.filter_by(user_id=uid).first() or Goal.query.filter_by(user_id=uid).first() or FinancialAccount.query.filter_by(user_id=uid).first():
        return {"error": "Demo data can only be loaded into an empty account."}, 409
    seed_user(uid)
    db.session.commit()
    return {"seeded": True}, 201


@api.post("/demo/reset")
@firebase_required()
def reset_demo():
    uid = current_user_id()
    clear_financial_data(uid)
    seed_user(uid)
    db.session.commit()
    return {"seeded": True, "reset": True}
