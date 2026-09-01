from calendar import monthrange
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from flask import Blueprint, jsonify, request
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db
from .firebase_auth import delete_firebase_identity, firebase_required, get_jwt_identity
from .models import Budget, FinancialAccount, Goal, Transaction, User
from .money import MAX_MONEY, ZERO, MoneyValidationError, as_decimal, json_money, money_sum, parse_money, percent

api = Blueprint("api", __name__, url_prefix="/api")
MAX_IMPORT_ROWS = 1000
ACCOUNT_TYPES = {"checking", "savings", "cash", "credit", "loan", "investment", "other"}
LIABILITY_ACCOUNT_TYPES = {"credit", "loan"}
LIQUID_ACCOUNT_TYPES = {"checking", "savings", "cash"}
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


def normalize_category(value):
    return " ".join(str(value or "").strip().split())


def category_key(value):
    return normalize_category(value).casefold()


def normalize_transaction_type(value, amount):
    raw = str(value or "").strip().lower()
    if raw in TRANSACTION_TYPES:
        return raw
    return "income" if amount > ZERO else "expense"


def account_map(uid):
    return {account.id: account for account in FinancialAccount.query.filter_by(user_id=uid).all()}


def account_balance(account):
    movement = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == account.user_id,
        Transaction.account_id == account.id,
    ).scalar()
    return (as_decimal(account.opening_balance) + as_decimal(movement)).quantize(Decimal("0.01"))


def serialize_account(account):
    balance = account_balance(account)
    liability = account.account_type in LIABILITY_ACCOUNT_TYPES
    opening = as_decimal(account.opening_balance)
    return {
        "id": account.id,
        "name": account.name,
        "type": account.account_type,
        "balanceRole": "liability" if liability else "asset",
        "institution": account.institution or "",
        # Liability opening balances are stored negative internally but entered as a normal positive debt amount.
        "openingBalance": json_money(abs(opening) if liability else opening),
        "currentBalance": json_money(balance),
        "netWorthContribution": json_money(balance),
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
    target = as_decimal(goal.target)
    saved = as_decimal(goal.saved)
    remaining = max(target - saved, ZERO)
    overfunded = max(saved - target, ZERO)
    completion = percent(saved, target)
    return {
        "id": goal.id,
        "name": goal.name,
        "target": json_money(target),
        "saved": json_money(saved),
        "targetDate": goal.target_date.isoformat() if goal.target_date else None,
        "notes": goal.notes or "",
        "amountRemaining": json_money(remaining),
        "percentComplete": float(completion),
        "isOverfunded": overfunded > ZERO,
        "overfundedBy": json_money(overfunded),
        "trackingOnly": True,
    }


def monthly_trend(transactions):
    result = []
    for year, month in month_keys(6):
        items = [item for item in transactions if item.date.year == year and item.date.month == month and item.transaction_type != "transfer"]
        income = money_sum(item.amount for item in items if item.transaction_type == "income")
        expenses = abs(money_sum(item.amount for item in items if item.transaction_type == "expense"))
        result.append({
            "month": date(year, month, 1).strftime("%b"),
            "income": json_money(income),
            "expenses": json_money(expenses),
            "net": json_money(income - expenses),
        })
    return result


def clear_financial_data(uid):
    Transaction.query.filter_by(user_id=uid).delete(synchronize_session=False)
    Budget.query.filter_by(user_id=uid).delete(synchronize_session=False)
    Goal.query.filter_by(user_id=uid).delete(synchronize_session=False)
    FinancialAccount.query.filter_by(user_id=uid).delete(synchronize_session=False)


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
        description = str(payload.get("description", existing.description if existing else "") or "").strip()
        include_in_totals = payload.get("includeInTotals", existing.include_in_totals if existing else True)
        archived = payload.get("archived", existing.archived if existing else False)
        if not isinstance(include_in_totals, bool) or not isinstance(archived, bool):
            return None

        if "openingBalance" in payload:
            opening_input = payload["openingBalance"]
        elif existing:
            previous = as_decimal(existing.opening_balance)
            opening_input = abs(previous) if existing.account_type in LIABILITY_ACCOUNT_TYPES else previous
        else:
            opening_input = ZERO
        opening_balance = parse_money(opening_input)
    except (MoneyValidationError, TypeError, ValueError):
        return None

    if not name or len(name) > 120 or account_type not in ACCOUNT_TYPES or len(institution) > 120 or len(description) > 500:
        return None
    if account_type in LIABILITY_ACCOUNT_TYPES:
        opening_balance = -abs(opening_balance)
    return name, account_type, institution, opening_balance, description, include_in_totals, archived


def parse_transaction_payload(payload, uid):
    try:
        description = str(payload["description"]).strip()
        amount = parse_money(payload["amount"], allow_zero=False)
        category = normalize_category(payload["category"])
        tx_date = datetime.strptime(str(payload["date"]), "%Y-%m-%d").date()
        notes = str(payload.get("notes", "")).strip()
        subcategory = normalize_category(payload.get("subcategory", ""))
    except (KeyError, MoneyValidationError, TypeError, ValueError):
        return None, "Description, non-zero decimal amount, category, and YYYY-MM-DD date are required."

    if not description or len(description) > 80 or not category or len(category) > 80 or len(notes) > 500 or len(subcategory) > 80:
        return None, "Description, non-zero decimal amount, category, and YYYY-MM-DD date are required."

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
    expenses = Transaction.query.filter(
        Transaction.user_id == uid,
        Transaction.transaction_type == "expense",
        Transaction.date >= start,
        Transaction.date <= end,
    ).all()
    spend_by_category = {}
    for item in expenses:
        key = category_key(item.category)
        spend_by_category[key] = spend_by_category.get(key, ZERO) + abs(as_decimal(item.amount))

    result = []
    for budget in budgets:
        limit = as_decimal(budget.limit)
        spent = spend_by_category.get(category_key(budget.category), ZERO)
        used = percent(spent, limit)
        status = "over" if used >= Decimal("100") else "approaching" if used >= Decimal("80") else "healthy"
        result.append({
            "id": budget.id,
            "category": budget.category,
            "limit": json_money(limit),
            "spent": json_money(spent),
            "remaining": json_money(limit - spent),
            "percentUsed": float(used),
            "status": status,
        })
    return result


def build_insights(month_income, month_expenses, categories, budgets, goals):
    insights = []
    if categories:
        top = max(categories.items(), key=lambda item: item[1][1])
        insights.append(f"{top[1][0]} is your largest spending category this month at ${top[1][1]:,.2f}.")
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
        insights.append(f"Your net cash flow is {'positive' if net >= ZERO else 'negative'} by ${abs(net):,.2f} this month.")
    if goals:
        nearest = min(goals, key=lambda goal: max(as_decimal(goal.target) - as_decimal(goal.saved), ZERO))
        remaining = max(as_decimal(nearest.target) - as_decimal(nearest.saved), ZERO)
        insights.append(f"You are ${remaining:,.2f} away from your {nearest.name} goal." if remaining else f"Your {nearest.name} goal is fully funded.")
    return insights[:4]


def seed_user(uid):
    checking = FinancialAccount(user_id=uid, name="Everyday Checking", account_type="checking", institution="Northstar Community Bank", opening_balance=Decimal("450.00"))
    savings = FinancialAccount(user_id=uid, name="Emergency Savings", account_type="savings", institution="Northstar Community Bank", opening_balance=Decimal("1200.00"))
    db.session.add_all([checking, savings])
    db.session.flush()

    for index, (year, month) in enumerate(month_keys(6)):
        day = min(18, monthrange(year, month)[1])
        tx_date = date(year, month, day)
        entries = [
            ("Paycheck", Decimal("3200.00") + Decimal(index * 45), "income", "Income", "Primary income"),
            ("Rent", Decimal("-1150.00"), "expense", "Housing", "Monthly rent"),
            ("Groceries", -(Decimal("245.00") + Decimal(index) * Decimal("7.50")), "expense", "Groceries", "Household groceries"),
            ("Utilities", -(Decimal("185.00") + Decimal(index * 4)), "expense", "Utilities", "Electric and water"),
        ]
        for description, amount, transaction_type, category, notes in entries:
            db.session.add(Transaction(user_id=uid, account_id=checking.id, description=description, amount=amount, transaction_type=transaction_type, category=category, date=tx_date, notes=notes))

    current = date.today()
    extras = [
        ("Freelance project", Decimal("1450.00"), "income", "Income", "One-off client work"),
        ("Fuel", Decimal("-96.70"), "expense", "Fuel", "Vehicle fuel"),
        ("Coffee shop", Decimal("-18.64"), "expense", "Dining", "Coffee with a friend"),
        ("Home internet", Decimal("-79.99"), "expense", "Utilities", "Monthly internet"),
        ("Streaming bundle", Decimal("-34.99"), "expense", "Subscriptions", "Monthly services"),
    ]
    for description, amount, transaction_type, category, notes in extras:
        db.session.add(Transaction(user_id=uid, account_id=checking.id, description=description, amount=amount, transaction_type=transaction_type, category=category, date=current, notes=notes))

    group = uuid4().hex
    db.session.add_all([
        Transaction(user_id=uid, account_id=checking.id, description="Savings transfer", amount=Decimal("-250.00"), transaction_type="transfer", category="Transfer", date=current, notes="Monthly savings", transfer_group=group),
        Transaction(user_id=uid, account_id=savings.id, description="Savings transfer", amount=Decimal("250.00"), transaction_type="transfer", category="Transfer", date=current, notes="Monthly savings", transfer_group=group),
    ])
    for category, limit in [("Groceries", "500.00"), ("Fuel", "250.00"), ("Subscriptions", "150.00"), ("Utilities", "350.00")]:
        db.session.add(Budget(user_id=uid, category=category, limit=Decimal(limit)))
    db.session.add_all([
        Goal(user_id=uid, name="Emergency fund", target=Decimal("6000.00"), saved=Decimal("2450.00"), notes="Six months of essential expenses"),
        Goal(user_id=uid, name="Weekend trip", target=Decimal("1200.00"), saved=Decimal("480.00"), notes="Travel and lodging"),
    ])


@api.get("/health")
def health():
    return {"status": "ok", "service": "ledgerly-api", "version": "1.3.0", "auth": "firebase", "money": "decimal"}


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
    if str((request.get_json(silent=True) or {}).get("confirmation", "")).strip() != "DELETE":
        return {"error": "Type DELETE to confirm permanent account deletion."}, 400

    try:
        clear_financial_data(user.id)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return {"error": "Ledgerly data could not be deleted. Nothing further was removed."}, 500

    try:
        delete_firebase_identity(user)
    except Exception:
        return {
            "error": "Ledgerly financial data was deleted, but the Firebase identity could not be removed. Sign in and retry account deletion or contact support.",
            "dataDeleted": True,
            "firebaseDeleted": False,
        }, 502

    try:
        db.session.delete(user)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return {
            "error": "Firebase identity and financial data were deleted, but Ledgerly account metadata still requires cleanup.",
            "dataDeleted": True,
            "firebaseDeleted": True,
            "metadataDeleted": False,
        }, 500
    return {"deleted": True, "dataDeleted": True, "firebaseDeleted": True, "metadataDeleted": True}


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
    transfer_count = Transaction.query.filter(
        Transaction.user_id == uid,
        Transaction.account_id == item.id,
        ((Transaction.transaction_type == "transfer") | (Transaction.transfer_group.is_not(None))),
    ).count()
    if transfer_count:
        return {"error": "Accounts with historical transfers cannot be hard-deleted. Archive the account to preserve both sides of each transfer.", "transferTransactionCount": transfer_count}, 409

    transaction_count = Transaction.query.filter_by(user_id=uid, account_id=item.id).count()
    detach = str(request.args.get("detach", "false")).lower() == "true"
    if transaction_count and not detach:
        return {"error": "This account has transactions. Archive it, or explicitly detach its non-transfer transactions before deleting it.", "transactionCount": transaction_count}, 409
    if transaction_count:
        Transaction.query.filter_by(user_id=uid, account_id=item.id).update({"account_id": None}, synchronize_session=False)
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
    month_income = money_sum(item.amount for item in month_items if item.transaction_type == "income")
    month_expenses = abs(money_sum(item.amount for item in month_items if item.transaction_type == "expense"))

    included_accounts = [item for item in accounts_serialized if item["includeInTotals"] and not item["archived"]]
    unassigned_balance = money_sum(item.amount for item in transactions if item.account_id is None)
    account_net_worth = money_sum(Decimal(str(item["currentBalance"])) for item in included_accounts)
    net_worth = account_net_worth + unassigned_balance
    available_balance = money_sum(
        Decimal(str(item["currentBalance"])) for item in included_accounts
        if item["type"] in LIQUID_ACCOUNT_TYPES
    )
    asset_balance = money_sum(
        max(Decimal(str(item["currentBalance"])), ZERO) for item in included_accounts
        if item["balanceRole"] == "asset"
    )
    liability_balance = money_sum(
        abs(min(Decimal(str(item["currentBalance"])), ZERO)) for item in included_accounts
        if item["balanceRole"] == "liability"
    )

    categories = {}
    for item in month_items:
        if item.transaction_type == "expense":
            key = category_key(item.category)
            label = normalize_category(item.category)
            prior_label, prior_amount = categories.get(key, (label, ZERO))
            categories[key] = (prior_label, prior_amount + abs(as_decimal(item.amount)))

    budgets = budget_payload(uid)
    goals = Goal.query.filter_by(user_id=uid).order_by(Goal.id.desc()).all()
    budget_categories = {category_key(item["category"]) for item in budgets}
    unbudgeted_spending = money_sum(amount for key, (_label, amount) in categories.items() if key not in budget_categories)
    budget_remaining = money_sum(Decimal(str(item["remaining"])) for item in budgets)
    net_cash_flow = month_income - month_expenses
    savings_rate = percent(net_cash_flow, month_income) if month_income else ZERO
    actual_expense_categories = sorted(
        ({"category": label, "amount": json_money(amount)} for label, amount in categories.values()),
        key=lambda item: item["amount"], reverse=True,
    )[:12]
    savings_contribution = money_sum(
        item.amount for item in transactions
        if start <= item.date <= end and item.transaction_type == "transfer" and as_decimal(item.amount) > ZERO
        and item.account_id in accounts_by_id and accounts_by_id[item.account_id].account_type == "savings"
    )
    days_remaining = max((end - date.today()).days + 1, 0)

    return {
        # totalBalance is retained for client compatibility; semantically it is net worth.
        "totalBalance": json_money(net_worth),
        "netWorth": json_money(net_worth),
        "availableBalance": json_money(available_balance),
        "assetBalance": json_money(asset_balance),
        "liabilityBalance": json_money(liability_balance),
        "income": json_money(month_income),
        "expenses": json_money(month_expenses),
        "netCashFlow": json_money(net_cash_flow),
        "savingsRate": float(savings_rate),
        "budgetRemaining": json_money(budget_remaining),
        "unbudgetedSpending": json_money(unbudgeted_spending),
        "categories": actual_expense_categories,
        "accounts": accounts_serialized,
        "transactions": [serialize_transaction(item, accounts_by_id) for item in transactions],
        "budgets": budgets,
        "goals": [serialize_goal(goal) for goal in goals],
        "monthlyTrend": monthly_trend(transactions),
        "monthlyPlan": {
            "expectedIncome": json_money(month_income),
            "actualIncome": json_money(month_income),
            "budgetedExpenses": json_money(money_sum(Decimal(str(item["limit"])) for item in budgets)),
            "actualExpenses": json_money(month_expenses),
            "amountRemaining": json_money(net_cash_flow),
            "unbudgetedSpending": json_money(unbudgeted_spending),
            "savingsContribution": json_money(savings_contribution),
            "netResult": json_money(net_cash_flow),
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
        amount = abs(parse_money(payload["amount"], allow_zero=False))
        tx_date = datetime.strptime(str(payload["date"]), "%Y-%m-%d").date()
        description = str(payload.get("description") or "Transfer").strip()
        notes = str(payload.get("notes") or "").strip()
    except (KeyError, MoneyValidationError, TypeError, ValueError):
        return {"error": "From account, to account, positive decimal amount, and YYYY-MM-DD date are required."}, 400
    if from_id == to_id or not description or len(description) > 80 or len(notes) > 500:
        return {"error": "Choose two different accounts and a positive transfer amount."}, 400
    source = FinancialAccount.query.filter_by(id=from_id, user_id=uid, archived=False).first()
    destination = FinancialAccount.query.filter_by(id=to_id, user_id=uid, archived=False).first()
    if not source or not destination:
        return {"error": "Both transfer accounts must belong to you and be active."}, 400

    group = uuid4().hex
    outgoing = Transaction(user_id=uid, account_id=source.id, description=description, amount=-amount, transaction_type="transfer", category="Transfer", date=tx_date, notes=notes, transfer_group=group)
    incoming = Transaction(user_id=uid, account_id=destination.id, description=description, amount=amount, transaction_type="transfer", category="Transfer", date=tx_date, notes=notes, transfer_group=group)
    try:
        db.session.add_all([outgoing, incoming])
        db.session.flush()
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return {"error": "Transfer could not be committed. No transfer entries were saved."}, 500
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
    if default_account and default_account.archived:
        return {"error": "Archived accounts cannot be used as an import destination."}, 400
    if not isinstance(rows, list) or not rows:
        return {"error": "Provide a non-empty transactions array."}, 400
    if len(rows) > MAX_IMPORT_ROWS:
        return {"error": f"Import is limited to {MAX_IMPORT_ROWS} rows at a time."}, 400

    existing = Transaction.query.filter_by(user_id=uid).all()
    fingerprints = {(item.description.strip().casefold(), as_decimal(item.amount), category_key(item.category), item.date.isoformat(), item.account_id) for item in existing}
    parsed_rows, invalid_rows, duplicate_rows = [], [], []
    for index, row in enumerate(rows, start=1):
        source = dict(row) if isinstance(row, dict) else {}
        if source.get("accountId") in (None, "") and default_account:
            source["accountId"] = default_account.id
        parsed, _error = parse_transaction_payload(source, uid)
        if not parsed:
            invalid_rows.append(index)
            continue
        fingerprint = (parsed["description"].casefold(), as_decimal(parsed["amount"]), category_key(parsed["category"]), parsed["date"].isoformat(), parsed["account_id"])
        if fingerprint in fingerprints:
            duplicate_rows.append(index)
            continue
        fingerprints.add(fingerprint)
        parsed_rows.append(parsed)

    if invalid_rows and not allow_partial:
        preview = ", ".join(str(index) for index in invalid_rows[:10])
        suffix = "…" if len(invalid_rows) > 10 else ""
        return {"error": f"Invalid transaction data on row(s): {preview}{suffix}", "invalidRows": invalid_rows, "importMode": "atomic"}, 400

    try:
        for parsed in parsed_rows:
            db.session.add(Transaction(user_id=uid, **parsed))
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return {"error": "Import failed while saving. No pending import rows were committed."}, 500
    return {
        "imported": len(parsed_rows),
        "invalidRows": invalid_rows,
        "skippedDuplicates": duplicate_rows,
        "duplicateRows": duplicate_rows,
        "importMode": "partial" if allow_partial else "atomic",
    }, 201


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
        deleted = Transaction.query.filter_by(user_id=uid, transfer_group=group).delete(synchronize_session=False)
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
        category = normalize_category(payload["category"])
        limit = parse_money(payload["limit"], allow_zero=False, allow_negative=False)
    except (KeyError, MoneyValidationError, TypeError, ValueError):
        return {"error": "Category and a positive decimal limit are required."}, 400
    if not category or len(category) > 80:
        return {"error": "Category and a positive decimal limit are required."}, 400
    existing = next((item for item in Budget.query.filter_by(user_id=uid).all() if category_key(item.category) == category_key(category)), None)
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
        limit = parse_money(payload["limit"], allow_zero=False, allow_negative=False)
    except (KeyError, MoneyValidationError, TypeError, ValueError):
        return {"error": "A positive decimal limit is required."}, 400
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
        target = parse_money(payload["target"], allow_zero=False, allow_negative=False)
        saved = parse_money(payload.get("saved", ZERO), allow_negative=False)
        notes = str(payload.get("notes", "") or "").strip()
        target_date = datetime.strptime(str(payload["targetDate"]), "%Y-%m-%d").date() if payload.get("targetDate") else None
    except (KeyError, MoneyValidationError, TypeError, ValueError):
        return {"error": "Name and a positive decimal target are required."}, 400
    if not name or len(name) > 120 or len(notes) > 2000:
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
        target = parse_money(payload.get("target", goal.target), allow_zero=False, allow_negative=False)
        saved = parse_money(payload.get("saved", goal.saved), allow_negative=False)
        notes = str(payload.get("notes", goal.notes or "") or "").strip()
        target_date = datetime.strptime(str(payload["targetDate"]), "%Y-%m-%d").date() if payload.get("targetDate") else (None if "targetDate" in payload else goal.target_date)
    except (MoneyValidationError, TypeError, ValueError):
        return {"error": "Invalid goal values."}, 400
    if not name or len(name) > 120 or len(notes) > 2000:
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
        amount = parse_money(payload["amount"], allow_zero=False, allow_negative=False)
    except (KeyError, MoneyValidationError, TypeError, ValueError):
        return {"error": "A positive decimal contribution is required."}, 400
    next_saved = as_decimal(goal.saved) + amount
    if next_saved > MAX_MONEY:
        return {"error": "Saved amount cannot exceed $999,999,999.99."}, 400
    goal.saved = next_saved
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
        "schemaVersion": 2,
        "moneySemantics": "decimal-2-half-up",
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
    if str((request.get_json(silent=True) or {}).get("confirmation", "")).strip() != "CLEAR":
        return {"error": "Type CLEAR to confirm deletion of all Ledgerly financial data."}, 400
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
    return {"seeded": True, "sampleData": True}, 201


@api.post("/demo/reset")
@firebase_required()
def reset_demo():
    uid = current_user_id()
    if str((request.get_json(silent=True) or {}).get("confirmation", "")).strip() != "RESET":
        return {"error": "Type RESET to replace all current financial data with fictional demo data."}, 400
    clear_financial_data(uid)
    seed_user(uid)
    db.session.commit()
    return {"seeded": True, "reset": True, "sampleData": True}
