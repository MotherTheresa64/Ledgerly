from calendar import monthrange
from datetime import UTC, date, datetime
from uuid import uuid4

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from .extensions import db
from .firebase_auth import firebase_required, get_jwt_identity
from .models import Budget, FinancialAccount, Goal, Transaction, User
from .money import (
    MAX_MONEY_CENTS,
    MoneyValidationError,
    cents_to_dollars,
    percent,
    to_cents,
)

api = Blueprint("api", __name__, url_prefix="/api")
MAX_IMPORT_ROWS = 1000
ACCOUNT_TYPES = {"checking", "savings", "cash", "credit", "loan", "investment", "other"}
TRANSACTION_TYPES = {"income", "expense", "transfer"}


def utc_today():
    return datetime.now(UTC).date()


def current_user_id():
    return int(get_jwt_identity())


def current_user():
    return db.session.get(User, current_user_id())


def parse_iso_date(value, *, label="Date"):
    try:
        parsed = date.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise ValueError(f"{label} must use YYYY-MM-DD.") from None
    if parsed.year < 1900:
        raise ValueError(f"{label} must be on or after 1900-01-01.")
    return parsed


def request_as_of_date():
    raw = request.args.get("asOf")
    if not raw:
        return utc_today()
    return parse_iso_date(raw, label="asOf")


def month_keys(count=6, as_of=None):
    anchor = as_of or utc_today()
    year, month = anchor.year, anchor.month
    items = []
    for _ in range(count):
        items.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(items))


def current_month_bounds(as_of=None):
    anchor = as_of or utc_today()
    return date(anchor.year, anchor.month, 1), date(
        anchor.year,
        anchor.month,
        monthrange(anchor.year, anchor.month)[1],
    )


def normalize_transaction_type(value, amount_cents):
    raw = str(value or "").strip().lower()
    if raw in TRANSACTION_TYPES:
        return raw
    return "income" if amount_cents > 0 else "expense"


def account_map(uid):
    return {account.id: account for account in FinancialAccount.query.filter_by(user_id=uid).all()}


def account_activity(uid):
    """Return account movement/count maps in one grouped query."""
    rows = db.session.query(
        Transaction.account_id,
        func.coalesce(func.sum(Transaction.amount_cents), 0),
        func.count(Transaction.id),
    ).filter(
        Transaction.user_id == uid,
        Transaction.account_id.isnot(None),
    ).group_by(Transaction.account_id).all()
    movements = {account_id: int(total or 0) for account_id, total, _count in rows}
    counts = {account_id: int(count or 0) for account_id, _total, count in rows}
    return movements, counts


def account_balance_cents(account, movements=None):
    if movements is None:
        movement = db.session.query(func.coalesce(func.sum(Transaction.amount_cents), 0)).filter(
            Transaction.user_id == account.user_id,
            Transaction.account_id == account.id,
        ).scalar()
        movement_cents = int(movement or 0)
    else:
        movement_cents = int(movements.get(account.id, 0))
    return int(account.opening_balance_cents or 0) + movement_cents


def serialize_account(account, movements=None, counts=None):
    transaction_count = counts.get(account.id, 0) if counts is not None else Transaction.query.filter_by(
        user_id=account.user_id,
        account_id=account.id,
    ).count()
    return {
        "id": account.id,
        "name": account.name,
        "type": account.account_type,
        "institution": account.institution or "",
        "openingBalance": cents_to_dollars(account.opening_balance_cents),
        "currentBalance": cents_to_dollars(account_balance_cents(account, movements)),
        "description": account.description or "",
        "includeInTotals": bool(account.include_in_totals),
        "archived": bool(account.archived),
        "transactionCount": int(transaction_count),
        "createdAt": account.created_at.isoformat() if account.created_at else None,
    }


def serialize_transaction(transaction, accounts=None):
    account = (accounts or {}).get(transaction.account_id) if transaction.account_id else None
    return transaction.to_dict(account.name if account else None)


def serialize_goal(goal):
    target_cents = int(goal.target_cents or 0)
    saved_cents = int(goal.saved_cents or 0)
    remaining_cents = max(target_cents - saved_cents, 0)
    return {
        "id": goal.id,
        "name": goal.name,
        "target": cents_to_dollars(target_cents),
        "saved": cents_to_dollars(saved_cents),
        "targetDate": goal.target_date.isoformat() if goal.target_date else None,
        "notes": goal.notes or "",
        "amountRemaining": cents_to_dollars(remaining_cents),
        "percentComplete": min(percent(saved_cents, target_cents), 100.0) if target_cents else 0.0,
    }


def monthly_trend(transactions, as_of=None):
    result = []
    for year, month in month_keys(6, as_of):
        items = [
            item
            for item in transactions
            if item.date.year == year and item.date.month == month and item.transaction_type != "transfer"
        ]
        income_cents = sum(
            item.amount_cents
            for item in items
            if item.transaction_type == "income" or (not item.transaction_type and item.amount_cents > 0)
        )
        expense_cents = abs(sum(
            item.amount_cents
            for item in items
            if item.transaction_type == "expense" or (not item.transaction_type and item.amount_cents < 0)
        ))
        result.append({
            "month": date(year, month, 1).strftime("%b"),
            "income": cents_to_dollars(income_cents),
            "expenses": cents_to_dollars(expense_cents),
            "net": cents_to_dollars(income_cents - expense_cents),
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
        opening_balance_cents = (
            to_cents(payload["openingBalance"], label="Opening balance")
            if "openingBalance" in payload
            else int(existing.opening_balance_cents if existing else 0)
        )
        description = str(payload.get("description", existing.description if existing else "") or "").strip()
        include_in_totals = payload.get("includeInTotals", existing.include_in_totals if existing else True)
        archived = payload.get("archived", existing.archived if existing else False)
        if not isinstance(include_in_totals, bool) or not isinstance(archived, bool):
            return None, "Include-in-totals and archived values must be true or false."
    except (KeyError, MoneyValidationError) as error:
        return None, str(error)

    if not name:
        return None, "Account name is required."
    if len(name) > 120:
        return None, "Account name cannot exceed 120 characters."
    if account_type not in ACCOUNT_TYPES:
        return None, "Choose a supported account type."
    if len(institution) > 120:
        return None, "Institution cannot exceed 120 characters."
    if len(description) > 500:
        return None, "Account description cannot exceed 500 characters."
    return (name, account_type, institution, opening_balance_cents, description, include_in_totals, archived), None


def parse_transaction_payload(payload, uid):
    try:
        description = str(payload["description"]).strip()
        raw_amount_cents = to_cents(payload["amount"], label="Transaction amount", allow_zero=False)
        category = str(payload["category"]).strip()
        tx_date = parse_iso_date(payload["date"])
        notes = str(payload.get("notes", "") or "").strip()
        subcategory = str(payload.get("subcategory", "") or "").strip()
    except KeyError:
        return None, "Description, non-zero amount, category, and YYYY-MM-DD date are required."
    except (MoneyValidationError, ValueError) as error:
        return None, str(error)

    if not description:
        return None, "Description is required."
    if len(description) > 80:
        return None, "Description cannot exceed 80 characters."
    if not category:
        return None, "Category is required."
    if len(category) > 80:
        return None, "Category cannot exceed 80 characters."
    if len(notes) > 500:
        return None, "Notes cannot exceed 500 characters."
    if len(subcategory) > 80:
        return None, "Subcategory cannot exceed 80 characters."

    transaction_type = normalize_transaction_type(payload.get("transactionType"), raw_amount_cents)
    if transaction_type == "transfer":
        return None, "Create transfers with the transfer workflow so both accounts stay balanced."
    amount_cents = abs(raw_amount_cents) if transaction_type == "income" else -abs(raw_amount_cents)

    account = owned_account(uid, payload.get("accountId"))
    if account is False:
        return None, "The selected account was not found."
    if account and account.archived:
        return None, "Archived accounts cannot receive new transactions."

    raw_tags = payload.get("tags", [])
    if isinstance(raw_tags, list):
        normalized_tags = []
        for raw_tag in raw_tags:
            tag = str(raw_tag).strip()
            if not tag:
                continue
            if len(tag) > 40:
                return None, "Each tag cannot exceed 40 characters."
            if tag not in normalized_tags:
                normalized_tags.append(tag)
        if len(normalized_tags) > 20:
            return None, "A transaction can have at most 20 tags."
        tags = ",".join(normalized_tags)
    else:
        tags = str(raw_tags or "").strip()
    if len(tags) > 500:
        return None, "Tags are too long."

    return {
        "description": description,
        "amount_cents": amount_cents,
        "transaction_type": transaction_type,
        "account_id": account.id if account else None,
        "category": category,
        "subcategory": subcategory or None,
        "tags": tags or None,
        "date": tx_date,
        "notes": notes,
    }, None


def budget_rows(uid, as_of=None):
    start, end = current_month_bounds(as_of)
    budgets = Budget.query.filter_by(user_id=uid).order_by(Budget.category.asc()).all()
    spending_rows = db.session.query(
        Transaction.category,
        func.coalesce(func.sum(func.abs(Transaction.amount_cents)), 0),
    ).filter(
        Transaction.user_id == uid,
        Transaction.transaction_type == "expense",
        Transaction.date >= start,
        Transaction.date <= end,
    ).group_by(Transaction.category).all()
    spending = {}
    for category, total in spending_rows:
        key = str(category).casefold()
        spending[key] = spending.get(key, 0) + int(total or 0)

    result = []
    for budget in budgets:
        limit_cents = int(budget.limit_cents or 0)
        spent_cents = spending.get(budget.category.casefold(), 0)
        percent_used = percent(spent_cents, limit_cents) if limit_cents else 0.0
        status = "over" if percent_used >= 100 else "approaching" if percent_used >= 80 else "healthy"
        result.append({
            "id": budget.id,
            "category": budget.category,
            "limit": cents_to_dollars(limit_cents),
            "spent": cents_to_dollars(spent_cents),
            "remaining": cents_to_dollars(limit_cents - spent_cents),
            "percentUsed": percent_used,
            "status": status,
            "_limitCents": limit_cents,
            "_spentCents": spent_cents,
            "_remainingCents": limit_cents - spent_cents,
        })
    return result


def public_budget(row):
    return {key: value for key, value in row.items() if not key.startswith("_")}


def budget_payload(uid, as_of=None):
    return [public_budget(row) for row in budget_rows(uid, as_of)]


def build_insights(month_income_cents, month_expense_cents, categories_cents, budgets, goals):
    insights = []
    if categories_cents:
        top_category, top_cents = max(categories_cents.items(), key=lambda item: item[1])
        insights.append(
            f"{top_category} is your largest spending category this month at "
            f"${cents_to_dollars(top_cents):,.2f}."
        )
    approaching = [item for item in budgets if item["status"] == "approaching"]
    over = [item for item in budgets if item["status"] == "over"]
    if over:
        insights.append(f"{len(over)} budget{'s are' if len(over) != 1 else ' is'} over the monthly limit.")
    elif approaching:
        insights.append(f"{len(approaching)} budget{'s are' if len(approaching) != 1 else ' is'} above 80% used.")
    elif budgets:
        insights.append("All active budgets are currently within their monthly limits.")
    if month_income_cents:
        net_cents = month_income_cents - month_expense_cents
        insights.append(
            f"Your net cash flow is {'positive' if net_cents >= 0 else 'negative'} by "
            f"${abs(cents_to_dollars(net_cents)):,.2f} this month."
        )
    if goals:
        nearest = min(goals, key=lambda goal: max(goal.target_cents - goal.saved_cents, 0))
        remaining_cents = max(nearest.target_cents - nearest.saved_cents, 0)
        if remaining_cents:
            insights.append(f"You are ${cents_to_dollars(remaining_cents):,.2f} away from your {nearest.name} goal.")
        else:
            insights.append(f"Your {nearest.name} goal is fully funded.")
    return insights[:4]


def create_account_record(
    uid,
    *,
    name,
    account_type,
    institution="",
    opening_cents=0,
    description="",
    include_in_totals=True,
    archived=False,
):
    item = FinancialAccount(
        user_id=uid,
        name=name,
        account_type=account_type,
        institution=institution,
        description=description,
        include_in_totals=include_in_totals,
        archived=archived,
        opening_balance=0,
        opening_balance_cents=0,
    )
    item.set_opening_balance_cents(opening_cents)
    return item


def create_transaction_record(uid, *, amount_cents, **kwargs):
    item = Transaction(user_id=uid, amount=0, amount_cents=0, **kwargs)
    item.set_amount_cents(amount_cents)
    return item


def create_budget_record(uid, *, category, limit_cents):
    item = Budget(user_id=uid, category=category, limit=0, limit_cents=0)
    item.set_limit_cents(limit_cents)
    return item


def create_goal_record(uid, *, name, target_cents, saved_cents=0, target_date=None, notes=""):
    item = Goal(
        user_id=uid,
        name=name,
        target=0,
        target_cents=0,
        saved=0,
        saved_cents=0,
        target_date=target_date,
        notes=notes,
    )
    item.set_target_cents(target_cents)
    item.set_saved_cents(saved_cents)
    return item


def seed_user(uid, as_of=None):
    checking = create_account_record(
        uid,
        name="Everyday Checking",
        account_type="checking",
        institution="Northstar Community Bank",
        opening_cents=45_000,
    )
    savings = create_account_record(
        uid,
        name="Emergency Savings",
        account_type="savings",
        institution="Northstar Community Bank",
        opening_cents=120_000,
    )
    db.session.add_all([checking, savings])
    db.session.flush()

    for index, (year, month) in enumerate(month_keys(6, as_of)):
        day = min(18, monthrange(year, month)[1])
        tx_date = date(year, month, day)
        entries = [
            ("Paycheck", 320_000 + index * 4_500, "income", "Income", "Primary income"),
            ("Rent", -115_000, "expense", "Housing", "Monthly rent"),
            ("Groceries", -(24_500 + index * 750), "expense", "Groceries", "Household groceries"),
            ("Utilities", -(18_500 + index * 400), "expense", "Utilities", "Electric and water"),
        ]
        for description, amount_cents, transaction_type, category, notes in entries:
            db.session.add(create_transaction_record(
                uid,
                account_id=checking.id,
                description=description,
                amount_cents=amount_cents,
                transaction_type=transaction_type,
                category=category,
                date=tx_date,
                notes=notes,
            ))

    current = as_of or utc_today()
    extras = [
        ("Freelance project", 145_000, "income", "Income", "One-off client work"),
        ("Fuel", -9_670, "expense", "Fuel", "Vehicle fuel"),
        ("Coffee shop", -1_864, "expense", "Dining", "Coffee with a friend"),
        ("Home internet", -7_999, "expense", "Utilities", "Monthly internet"),
        ("Streaming bundle", -3_499, "expense", "Subscriptions", "Monthly services"),
    ]
    for description, amount_cents, transaction_type, category, notes in extras:
        db.session.add(create_transaction_record(
            uid,
            account_id=checking.id,
            description=description,
            amount_cents=amount_cents,
            transaction_type=transaction_type,
            category=category,
            date=current,
            notes=notes,
        ))

    group = uuid4().hex
    db.session.add_all([
        create_transaction_record(
            uid,
            account_id=checking.id,
            description="Savings transfer",
            amount_cents=-25_000,
            transaction_type="transfer",
            category="Transfer",
            date=current,
            notes="Monthly savings",
            transfer_group=group,
        ),
        create_transaction_record(
            uid,
            account_id=savings.id,
            description="Savings transfer",
            amount_cents=25_000,
            transaction_type="transfer",
            category="Transfer",
            date=current,
            notes="Monthly savings",
            transfer_group=group,
        ),
    ])
    for category, limit_cents in [
        ("Groceries", 50_000),
        ("Fuel", 25_000),
        ("Subscriptions", 15_000),
        ("Utilities", 35_000),
    ]:
        db.session.add(create_budget_record(uid, category=category, limit_cents=limit_cents))
    db.session.add_all([
        create_goal_record(
            uid,
            name="Emergency fund",
            target_cents=600_000,
            saved_cents=245_000,
            notes="Six months of essential expenses",
        ),
        create_goal_record(
            uid,
            name="Weekend trip",
            target_cents=120_000,
            saved_cents=48_000,
            notes="Travel and lodging",
        ),
    ])


@api.get("/health")
def health():
    return {
        "status": "ok",
        "service": "ledgerly-api",
        "version": "1.3.0",
        "auth": "firebase",
        "moneyStorage": "integer-cents",
    }


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
        movements, counts = account_activity(uid)
        items = FinancialAccount.query.filter_by(user_id=uid).order_by(
            FinancialAccount.archived.asc(),
            FinancialAccount.name.asc(),
        ).all()
        return jsonify([serialize_account(item, movements, counts) for item in items])

    parsed, error = parse_account_payload(request.get_json(silent=True) or {})
    if not parsed:
        return {"error": error or "Invalid account values."}, 400
    name, account_type, institution, opening_cents, description, include_in_totals, archived = parsed
    item = create_account_record(
        uid,
        name=name,
        account_type=account_type,
        institution=institution,
        opening_cents=opening_cents,
        description=description,
        include_in_totals=include_in_totals,
        archived=archived,
    )
    db.session.add(item)
    db.session.commit()
    movements, counts = account_activity(uid)
    return serialize_account(item, movements, counts), 201


@api.patch("/accounts/<int:account_id>")
@firebase_required()
def update_account(account_id):
    uid = current_user_id()
    item = FinancialAccount.query.filter_by(id=account_id, user_id=uid).first_or_404()
    parsed, error = parse_account_payload(request.get_json(silent=True) or {}, item)
    if not parsed:
        return {"error": error or "Invalid account values."}, 400
    name, account_type, institution, opening_cents, description, include_in_totals, archived = parsed
    item.name = name
    item.account_type = account_type
    item.institution = institution
    item.description = description
    item.include_in_totals = include_in_totals
    item.archived = archived
    item.set_opening_balance_cents(opening_cents)
    db.session.commit()
    movements, counts = account_activity(uid)
    return serialize_account(item, movements, counts)


@api.delete("/accounts/<int:account_id>")
@firebase_required()
def delete_financial_account(account_id):
    uid = current_user_id()
    item = FinancialAccount.query.filter_by(id=account_id, user_id=uid).first_or_404()
    transaction_count = Transaction.query.filter_by(user_id=uid, account_id=item.id).count()
    detach = str(request.args.get("detach", "false")).lower() == "true"
    if transaction_count and not detach:
        return {
            "error": "This account has transactions. Archive it, or explicitly detach its transactions before deleting it.",
            "transactionCount": transaction_count,
        }, 409
    if transaction_count:
        Transaction.query.filter_by(user_id=uid, account_id=item.id).update(
            {"account_id": None},
            synchronize_session=False,
        )
    db.session.delete(item)
    db.session.commit()
    return {"deleted": account_id, "detachedTransactions": transaction_count}


@api.get("/dashboard")
@firebase_required()
def dashboard():
    uid = current_user_id()
    try:
        as_of = request_as_of_date()
    except ValueError as error:
        return {"error": str(error)}, 400

    accounts_by_id = account_map(uid)
    movements, counts = account_activity(uid)
    account_items = sorted(accounts_by_id.values(), key=lambda item: (item.archived, item.name.lower()))
    accounts_serialized = [serialize_account(item, movements, counts) for item in account_items]
    transactions = Transaction.query.filter_by(user_id=uid).order_by(
        Transaction.date.desc(),
        Transaction.id.desc(),
    ).all()
    start, end = current_month_bounds(as_of)
    month_items = [item for item in transactions if start <= item.date <= end and item.transaction_type != "transfer"]
    month_income_cents = sum(
        item.amount_cents
        for item in month_items
        if item.transaction_type == "income" or (not item.transaction_type and item.amount_cents > 0)
    )
    month_expense_cents = abs(sum(
        item.amount_cents
        for item in month_items
        if item.transaction_type == "expense" or (not item.transaction_type and item.amount_cents < 0)
    ))

    if accounts_serialized:
        tracked_balance_cents = sum(
            account_balance_cents(account, movements)
            for account in account_items
            if account.include_in_totals and not account.archived
        )
        unassigned_balance_cents = sum(item.amount_cents for item in transactions if item.account_id is None)
        total_balance_cents = tracked_balance_cents + unassigned_balance_cents
    else:
        total_balance_cents = sum(item.amount_cents for item in transactions)

    category_totals = {}
    category_labels = {}
    for item in month_items:
        if item.transaction_type == "expense" or (not item.transaction_type and item.amount_cents < 0):
            key = item.category.casefold()
            category_labels.setdefault(key, item.category)
            category_totals[key] = category_totals.get(key, 0) + abs(item.amount_cents)
    categories_cents = {category_labels[key]: amount for key, amount in category_totals.items()}

    budget_internal = budget_rows(uid, as_of)
    budgets_public = [public_budget(row) for row in budget_internal]
    goals = Goal.query.filter_by(user_id=uid).order_by(Goal.id.desc()).all()
    budget_categories = {item["category"].casefold() for item in budget_internal}
    unbudgeted_spending_cents = sum(
        amount for key, amount in category_totals.items() if key not in budget_categories
    )
    budget_remaining_cents = sum(item["_remainingCents"] for item in budget_internal)
    net_cash_flow_cents = month_income_cents - month_expense_cents
    savings_rate = percent(net_cash_flow_cents, month_income_cents) if month_income_cents else 0.0
    actual_expense_categories = sorted(
        (
            {"category": category_labels[key], "amount": cents_to_dollars(value)}
            for key, value in category_totals.items()
        ),
        key=lambda item: item["amount"],
        reverse=True,
    )[:12]
    savings_contribution_cents = sum(
        item.amount_cents
        for item in transactions
        if start <= item.date <= end
        and item.transaction_type == "transfer"
        and item.amount_cents > 0
        and item.account_id in accounts_by_id
        and accounts_by_id[item.account_id].account_type == "savings"
    )
    days_remaining = max((end - as_of).days + 1, 0)

    return {
        "asOf": as_of.isoformat(),
        "totalBalance": cents_to_dollars(total_balance_cents),
        "availableBalance": cents_to_dollars(total_balance_cents),
        "income": cents_to_dollars(month_income_cents),
        "expenses": cents_to_dollars(month_expense_cents),
        "netCashFlow": cents_to_dollars(net_cash_flow_cents),
        "savingsRate": savings_rate,
        "budgetRemaining": cents_to_dollars(budget_remaining_cents),
        "unbudgetedSpending": cents_to_dollars(unbudgeted_spending_cents),
        "categories": actual_expense_categories,
        "accounts": accounts_serialized,
        "transactions": [serialize_transaction(item, accounts_by_id) for item in transactions],
        "budgets": budgets_public,
        "goals": [serialize_goal(goal) for goal in goals],
        "monthlyTrend": monthly_trend(transactions, as_of),
        "monthlyPlan": {
            "expectedIncome": cents_to_dollars(month_income_cents),
            "actualIncome": cents_to_dollars(month_income_cents),
            "budgetedExpenses": cents_to_dollars(sum(item["_limitCents"] for item in budget_internal)),
            "actualExpenses": cents_to_dollars(month_expense_cents),
            "amountRemaining": cents_to_dollars(net_cash_flow_cents),
            "unbudgetedSpending": cents_to_dollars(unbudgeted_spending_cents),
            "savingsContribution": cents_to_dollars(savings_contribution_cents),
            "netResult": cents_to_dollars(net_cash_flow_cents),
            "daysRemaining": days_remaining,
        },
        "insights": build_insights(
            month_income_cents,
            month_expense_cents,
            categories_cents,
            budgets_public,
            goals,
        ),
    }


@api.route("/transactions", methods=["GET", "POST"])
@firebase_required()
def transactions():
    uid = current_user_id()
    if request.method == "GET":
        accounts_by_id = account_map(uid)
        items = Transaction.query.filter_by(user_id=uid).order_by(
            Transaction.date.desc(),
            Transaction.id.desc(),
        ).all()
        return jsonify([serialize_transaction(item, accounts_by_id) for item in items])

    parsed, error = parse_transaction_payload(request.get_json(silent=True) or {}, uid)
    if not parsed:
        return {"error": error}, 400
    amount_cents = parsed.pop("amount_cents")
    item = create_transaction_record(uid, amount_cents=amount_cents, **parsed)
    db.session.add(item)
    db.session.commit()
    return serialize_transaction(item, account_map(uid)), 201


@api.post("/transfers")
@firebase_required()
def create_transfer():
    uid = current_user_id()
    payload = request.get_json(silent=True) or {}
    try:
        from_id = int(payload["fromAccountId"])
        to_id = int(payload["toAccountId"])
        amount_cents = abs(to_cents(payload["amount"], label="Transfer amount", allow_zero=False))
        tx_date = parse_iso_date(payload["date"])
        description = str(payload.get("description") or "Transfer").strip()
        notes = str(payload.get("notes") or "").strip()
    except KeyError:
        return {"error": "From account, to account, positive amount, and YYYY-MM-DD date are required."}, 400
    except (TypeError, ValueError, MoneyValidationError) as error:
        return {"error": str(error)}, 400

    if from_id == to_id:
        return {"error": "Choose two different accounts for a transfer."}, 400
    if not description or len(description) > 80:
        return {"error": "Transfer description must be between 1 and 80 characters."}, 400
    if len(notes) > 500:
        return {"error": "Notes cannot exceed 500 characters."}, 400

    source = FinancialAccount.query.filter_by(id=from_id, user_id=uid, archived=False).first()
    destination = FinancialAccount.query.filter_by(id=to_id, user_id=uid, archived=False).first()
    if not source or not destination:
        return {"error": "Both transfer accounts must belong to you and be active."}, 400

    group = uuid4().hex
    outgoing = create_transaction_record(
        uid,
        account_id=source.id,
        description=description,
        amount_cents=-amount_cents,
        transaction_type="transfer",
        category="Transfer",
        date=tx_date,
        notes=notes,
        transfer_group=group,
    )
    incoming = create_transaction_record(
        uid,
        account_id=destination.id,
        description=description,
        amount_cents=amount_cents,
        transaction_type="transfer",
        category="Transfer",
        date=tx_date,
        notes=notes,
        transfer_group=group,
    )
    db.session.add_all([outgoing, incoming])
    db.session.commit()
    accounts_by_id = {source.id: source, destination.id: destination}
    return {
        "transferGroup": group,
        "transactions": [
            serialize_transaction(outgoing, accounts_by_id),
            serialize_transaction(incoming, accounts_by_id),
        ],
    }, 201


@api.post("/transactions/import")
@firebase_required()
def import_transactions():
    uid = current_user_id()
    payload = request.get_json(silent=True) or {}
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
    fingerprints = {
        (
            item.description.strip().lower(),
            item.amount_cents,
            item.category.strip().lower(),
            item.date.isoformat(),
            item.account_id,
        )
        for item in existing
    }
    parsed_rows, invalid_rows, duplicate_rows = [], [], []
    for index, row in enumerate(rows, start=1):
        source = dict(row) if isinstance(row, dict) else {}
        if source.get("accountId") in (None, "") and default_account:
            source["accountId"] = default_account.id
        parsed, _error = parse_transaction_payload(source, uid)
        if not parsed:
            invalid_rows.append(index)
            continue
        fingerprint = (
            parsed["description"].lower(),
            parsed["amount_cents"],
            parsed["category"].lower(),
            parsed["date"].isoformat(),
            parsed["account_id"],
        )
        if fingerprint in fingerprints:
            duplicate_rows.append(index)
            continue
        fingerprints.add(fingerprint)
        parsed_rows.append(parsed)

    if invalid_rows and not allow_partial:
        preview = ", ".join(str(index) for index in invalid_rows[:10])
        suffix = "…" if len(invalid_rows) > 10 else ""
        return {
            "error": f"Invalid transaction data on row(s): {preview}{suffix}",
            "invalidRows": invalid_rows,
        }, 400

    for parsed in parsed_rows:
        amount_cents = parsed.pop("amount_cents")
        db.session.add(create_transaction_record(uid, amount_cents=amount_cents, **parsed))
    db.session.commit()
    return {
        "imported": len(parsed_rows),
        "invalidRows": invalid_rows,
        "skippedDuplicates": duplicate_rows,
        "duplicateRows": duplicate_rows,
    }, 201


@api.patch("/transactions/<int:transaction_id>")
@firebase_required()
def update_transaction(transaction_id):
    uid = current_user_id()
    item = Transaction.query.filter_by(id=transaction_id, user_id=uid).first_or_404()
    if item.transaction_type == "transfer" or item.transfer_group:
        return {
            "error": "Transfers are paired entries. Delete and recreate the transfer instead of editing one side."
        }, 409
    parsed, error = parse_transaction_payload(request.get_json(silent=True) or {}, uid)
    if not parsed:
        return {"error": error}, 400
    amount_cents = parsed.pop("amount_cents")
    for key, value in parsed.items():
        setattr(item, key, value)
    item.set_amount_cents(amount_cents)
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
        return {
            "deleted": transaction_id,
            "deletedTransferEntries": deleted,
            "transferGroup": group,
        }
    db.session.delete(item)
    db.session.commit()
    return {"deleted": transaction_id}


@api.route("/budgets", methods=["GET", "POST"])
@firebase_required()
def budgets():
    uid = current_user_id()
    try:
        as_of = request_as_of_date()
    except ValueError as error:
        return {"error": str(error)}, 400
    if request.method == "GET":
        return jsonify(budget_payload(uid, as_of))

    payload = request.get_json(silent=True) or {}
    try:
        category = str(payload["category"]).strip()
        limit_cents = to_cents(
            payload["limit"],
            label="Monthly budget",
            allow_zero=False,
            allow_negative=False,
        )
    except KeyError:
        return {"error": "Category and a positive limit are required."}, 400
    except MoneyValidationError as error:
        return {"error": str(error)}, 400
    if not category or len(category) > 80:
        return {"error": "Category must be between 1 and 80 characters."}, 400

    existing = Budget.query.filter(
        Budget.user_id == uid,
        func.lower(Budget.category) == category.lower(),
    ).first()
    if existing:
        existing.set_limit_cents(limit_cents)
        budget, status = existing, 200
    else:
        budget, status = create_budget_record(
            uid,
            category=category,
            limit_cents=limit_cents,
        ), 201
        db.session.add(budget)
    db.session.commit()
    return next(item for item in budget_payload(uid, as_of) if item["id"] == budget.id), status


@api.patch("/budgets/<int:budget_id>")
@firebase_required()
def update_budget(budget_id):
    uid = current_user_id()
    budget = Budget.query.filter_by(id=budget_id, user_id=uid).first_or_404()
    payload = request.get_json(silent=True) or {}
    try:
        limit_cents = to_cents(
            payload["limit"],
            label="Monthly budget",
            allow_zero=False,
            allow_negative=False,
        )
        as_of = request_as_of_date()
    except KeyError:
        return {"error": "A positive limit is required."}, 400
    except (MoneyValidationError, ValueError) as error:
        return {"error": str(error)}, 400
    budget.set_limit_cents(limit_cents)
    db.session.commit()
    return next(item for item in budget_payload(uid, as_of) if item["id"] == budget.id)


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
        return jsonify([
            serialize_goal(goal)
            for goal in Goal.query.filter_by(user_id=uid).order_by(Goal.id.desc()).all()
        ])

    payload = request.get_json(silent=True) or {}
    try:
        name = str(payload["name"]).strip()
        target_cents = to_cents(
            payload["target"],
            label="Goal target",
            allow_zero=False,
            allow_negative=False,
        )
        saved_cents = to_cents(
            payload.get("saved", 0),
            label="Saved amount",
            allow_negative=False,
        )
        notes = str(payload.get("notes", "") or "").strip()
        target_date = parse_iso_date(payload["targetDate"], label="Target date") if payload.get("targetDate") else None
    except KeyError:
        return {"error": "Name and a positive target are required."}, 400
    except (MoneyValidationError, ValueError) as error:
        return {"error": str(error)}, 400
    if not name or len(name) > 120 or len(notes) > 2000:
        return {
            "error": "Goal name must be 1–120 characters and notes cannot exceed 2,000 characters."
        }, 400

    goal = create_goal_record(
        uid,
        name=name,
        target_cents=target_cents,
        saved_cents=saved_cents,
        target_date=target_date,
        notes=notes,
    )
    db.session.add(goal)
    db.session.commit()
    return serialize_goal(goal), 201


@api.patch("/goals/<int:goal_id>")
@firebase_required()
def update_goal(goal_id):
    goal = Goal.query.filter_by(id=goal_id, user_id=current_user_id()).first_or_404()
    payload = request.get_json(silent=True) or {}
    try:
        name = str(payload.get("name", goal.name)).strip()
        target_cents = (
            to_cents(
                payload["target"],
                label="Goal target",
                allow_zero=False,
                allow_negative=False,
            )
            if "target" in payload
            else int(goal.target_cents)
        )
        saved_cents = (
            to_cents(
                payload["saved"],
                label="Saved amount",
                allow_negative=False,
            )
            if "saved" in payload
            else int(goal.saved_cents)
        )
        notes = str(payload.get("notes", goal.notes or "") or "").strip()
        target_date = (
            parse_iso_date(payload["targetDate"], label="Target date")
            if payload.get("targetDate")
            else (None if "targetDate" in payload else goal.target_date)
        )
    except (MoneyValidationError, ValueError) as error:
        return {"error": str(error)}, 400
    if not name or len(name) > 120 or len(notes) > 2000:
        return {
            "error": "Goal name must be 1–120 characters and notes cannot exceed 2,000 characters."
        }, 400

    goal.name = name
    goal.target_date = target_date
    goal.notes = notes
    goal.set_target_cents(target_cents)
    goal.set_saved_cents(saved_cents)
    db.session.commit()
    return serialize_goal(goal)


@api.post("/goals/<int:goal_id>/contribute")
@firebase_required()
def contribute_goal(goal_id):
    goal = Goal.query.filter_by(id=goal_id, user_id=current_user_id()).first_or_404()
    payload = request.get_json(silent=True) or {}
    try:
        contribution_cents = to_cents(
            payload["amount"],
            label="Contribution",
            allow_zero=False,
            allow_negative=False,
        )
    except KeyError:
        return {"error": "A positive contribution is required."}, 400
    except MoneyValidationError as error:
        return {"error": str(error)}, 400
    next_saved_cents = int(goal.saved_cents) + contribution_cents
    if next_saved_cents > MAX_MONEY_CENTS:
        return {"error": "Saved amount cannot exceed $999,999,999.99."}, 400
    goal.set_saved_cents(next_saved_cents)
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
    try:
        as_of = request_as_of_date()
    except ValueError as error:
        return {"error": str(error)}, 400
    accounts_by_id = account_map(uid)
    movements, counts = account_activity(uid)
    return {
        "exportedAt": datetime.now(UTC).isoformat(),
        "accounts": [serialize_account(item, movements, counts) for item in accounts_by_id.values()],
        "transactions": [
            serialize_transaction(item, accounts_by_id)
            for item in Transaction.query.filter_by(user_id=uid).order_by(
                Transaction.date.desc(),
                Transaction.id.desc(),
            ).all()
        ],
        "budgets": budget_payload(uid, as_of),
        "goals": [
            serialize_goal(goal)
            for goal in Goal.query.filter_by(user_id=uid).order_by(Goal.id.desc()).all()
        ],
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
    if (
        Transaction.query.filter_by(user_id=uid).first()
        or Budget.query.filter_by(user_id=uid).first()
        or Goal.query.filter_by(user_id=uid).first()
        or FinancialAccount.query.filter_by(user_id=uid).first()
    ):
        return {"error": "Demo data can only be loaded into an empty account."}, 409
    try:
        as_of = request_as_of_date()
    except ValueError as error:
        return {"error": str(error)}, 400
    seed_user(uid, as_of)
    db.session.commit()
    return {"seeded": True}, 201


@api.post("/demo/reset")
@firebase_required()
def reset_demo():
    uid = current_user_id()
    try:
        as_of = request_as_of_date()
    except ValueError as error:
        return {"error": str(error)}, 400
    clear_financial_data(uid)
    seed_user(uid, as_of)
    db.session.commit()
    return {"seeded": True, "reset": True}
