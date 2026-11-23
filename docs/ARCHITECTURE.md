# Ledgerly architecture

## Overview

Ledgerly is a full-stack monorepo with a React/TypeScript SPA, Firebase Authentication, a Flask REST API, and PostgreSQL persistence:

- `client/` — product UI, Firebase browser authentication, client-side interaction state, CSV helpers, and typed API access
- Firebase Authentication — registration, login, email verification, password recovery, and credential lifecycle
- `server/` — Firebase ID-token verification, finance-domain validation, persistence, analytics, and account-data APIs
- `server/app/firebase_auth.py` — Firebase Admin verification and Firebase UID → Ledgerly user mapping
- `server/app/models.py` — relational finance-domain models
- `server/app/routes.py` — user-scoped REST endpoints and derived finance read models
- `server/tests/` — 43 pytest cases: API, security, ownership, accounts/transfers, import, money, schema-upgrade, and CRUD (in-memory SQLite, no network)
- `.github/workflows/ci.yml` — frontend dependency audit/typecheck/build plus backend tests on Python 3.12 and 3.14
- `render.yaml` — PostgreSQL, API, static frontend, and health-check deployment definition

## Identity boundary

Firebase is the credential authority; Ledgerly is the finance-data authority.

```text
React browser app
    │
    ├── Firebase Authentication
    │      ├── email/password registration
    │      ├── sign-in
    │      ├── verification email
    │      ├── password reset
    │      └── reauthentication/password change
    │
    └── current Firebase ID token
               │ Authorization: Bearer ...
               ▼
          Flask API
               │ Firebase Admin verifies token
               │ resolves Firebase UID
               ▼
        internal Ledgerly User
               │
               ▼
           PostgreSQL
```

The Flask API does not receive a user's Firebase login password. A verified Firebase token is converted into one internal Ledgerly user id, and that internal id is used for all finance ownership queries.

## Identity mapping and migration

`User.firebase_uid` stores the Firebase identity mapping.

On the first authenticated API call:

1. Firebase Admin verifies the bearer token.
2. Ledgerly reads `uid`, `email`, and `email_verified` from the verified claims.
3. If `firebase_uid` already exists, that Ledgerly user is loaded.
4. Otherwise, a pre-Firebase Ledgerly user with the same **verified** email can be linked to the Firebase UID, preserving existing transactions, budgets, goals, and account creation history.
5. If no Ledgerly record exists, one is created.

A second Firebase UID cannot claim an email that has already been mapped to another Firebase UID.

The deployed database still contains a legacy non-null `password_hash` column from Ledgerly's first authentication implementation. New Firebase users receive a random unusable placeholder only to satisfy that historical schema constraint. The value is never used to authenticate.

## Domain model

A `User` owns `FinancialAccount`, `Transaction`, `Budget`, and `Goal` records (`server/app/models.py`). Every child table has an indexed `user_id`.

- `FinancialAccount` (checking, savings, cash, credit, loan, investment, other) has an opening balance, `include_in_totals`, and an `archived` flag. Its current balance is derived: opening balance plus the sum of its transactions.
- `Transaction` stores signed values: positive is income, negative is expense, with an explicit `transaction_type` of `income`, `expense` or `transfer`. The UI hides the sign behind Income / Expense controls. `account_id` is nullable (unassigned transactions are allowed).
- `Budget` stores one monthly limit per category. Spent and remaining amounts are derived from current-month expense transactions, matched to the category case-insensitively. There is no database unique constraint on `(user_id, category)`; the upsert in `POST /api/budgets` compares the exact string.
- `Goal` stores a target amount and current saved amount. Contributions are applied through a dedicated authenticated endpoint.

### Decimal money

All money columns (`financial_account.opening_balance`, `transaction.amount`, `budget.limit`, `goal.target`, `goal.saved`) are `NUMERIC(12,2)` (`MONEY` in `models.py`). Inputs are parsed by `money()` in `routes.py` to `Decimal` rounded half-up to cents; SQL sums are normalised by `cents()` (SQLite returns floats for `SUM`). The JSON API still emits plain numbers (`float(cents(x))`), so the client never handles strings. A request-level guard in `create_app` (`oversized_money_value`) rejects values above 999,999,999.99 or non-finite numbers before routing.

Existing PostgreSQL databases that still have `double precision` money columns are converted in place on startup by `ensure_money_schema()` (`server/app/__init__.py`, `USING round(col::numeric, 2)`); SQLite needs nothing. The other startup helpers `ensure_auth_schema()` and `ensure_finance_schema()` add missing columns and indexes with `ALTER TABLE`. There is no migration tool (Alembic is not used): schema evolution is additive, idempotent code run on every boot.

### Transfers

`POST /api/transfers` writes two `Transaction` rows in one commit, a negative row on the source account and a positive row on the destination, tagged with a shared `transfer_group` UUID and `transaction_type="transfer"`. Both accounts must belong to the caller and be unarchived. Transfers are excluded from monthly income, expenses, categories and trend, so they move balances without changing cash flow. A transfer side cannot be edited (409); deleting either side deletes the whole group.

The application deliberately derives analytics from source records instead of persisting duplicate aggregates.

## Dashboard read model

`GET /api/dashboard` returns the main product read model in one authenticated request:

- lifetime net balance
- current-month income, expenses, and savings rate
- current-month category spending
- current-month budget progress and remaining amounts
- complete transaction history
- savings goals
- six-month income / expense / net trend

This keeps finance calculations in one place and gives the React client a stable presentation contract.

## Current-month semantics

Ledgerly distinguishes between lifetime and monthly values:

- **Net balance** is the sum of all tracked transactions.
- **Income, expenses, savings rate, category spending, and budget progress** are calculated for the active calendar month.
- **Trend data** covers the current month plus the previous five months.

## API design

Authentication endpoints are not implemented by Flask. Firebase's browser SDK owns registration/login/recovery and the Firebase Admin SDK protects the finance API.

### Account data

- `GET /api/account` returns the mapped Ledgerly account summary.
- Password changes are performed by Firebase after reauthentication.
- Account deletion reauthenticates with Firebase in the client, deletes Ledgerly finance/account data through the API, then deletes the Firebase user.

### Transactions

- Create, list, update, and delete
- Optional notes
- Atomic validated bulk import (maximum 1,000 rows per request)
- Every item lookup includes the authenticated internal `user_id`

### Budgets

- Create/upsert by category (exact-string match), update limit, delete
- Current-month spent/remaining/status (`healthy` under 80%, `approaching` from 80%, `over` from 100%) are calculated at read time

### Goals

- Create, update, delete
- Direct positive contributions
- Completion is derived from `saved >= target`

### Accounts, transfers, export

- `GET/POST /api/accounts`, `PATCH/DELETE /api/accounts/:id`. Deleting an account that has transactions returns 409 unless `?detach=true`, which sets those transactions' `account_id` to NULL. A transaction on an archived account can still be edited, but cannot be moved onto one.
- `POST /api/transfers` (see above)
- `GET /api/export` returns accounts, transactions, budgets and goals as JSON (the client's full backup)

### Data tools

- Clear finance data while keeping the account
- Seed a completely empty account with realistic sample data
- Reset any account to the six-month sample dataset for evaluation

## Browser authentication behavior

The browser persists Firebase Authentication through the Firebase SDK. Ledgerly also keeps a short-lived `ledgerly_token` marker for its existing top-level UI gate, but API authorization does not trust that stored marker.

Before every protected request, the API client waits for Firebase auth state to initialize and calls `getIdToken()` on the active Firebase user. That current token is sent as the bearer credential. If the API responds with `401`, the UI session marker is cleared and the user is returned to authentication.

When the Ledgerly UI signs out, it clears its marker; the authentication screen then closes any verified Firebase persisted session so sign-out is complete.

## Ownership and authorization

Resource-level authorization is enforced server-side, not trusted to the UI. Transaction, budget, and goal updates/deletes query by both object ID and the internal Ledgerly user ID produced only after Firebase token verification. Tests explicitly verify that one Firebase identity cannot read, edit, or delete another user's records through guessed IDs.

## Validation and import safety

Mutation payloads are validated on the server for required fields, non-zero transaction amounts, positive budget/goal values, string length limits (description 80, notes 500), and ISO dates. `PATCH /api/transactions/:id` keeps stored values for optional fields (`notes`, `subcategory`, `tags`, `accountId`) the client did not send.

CSV is parsed in the browser into the same typed transaction payload used by normal creation. `POST /api/transactions/import` (max 1,000 rows) validates every row and drops duplicates (same description, amount, category, date and account, compared case-insensitively against existing rows and earlier rows of the same file). The server default is all-or-nothing: with any invalid row nothing is saved and the response lists `invalidRows`. The client sends `allowPartial: true`, in which case valid rows are committed in one commit and invalid and duplicate row numbers are reported back.

## Database strategy

`DATABASE_URL` controls persistence:

- local development defaults to SQLite
- production uses PostgreSQL

PostgreSQL connection strings supplied by hosting providers are normalized to the Psycopg SQLAlchemy driver in `config.py`.

## Frontend product areas

1. **Overview** — lifetime balance, monthly KPIs, six-month trend, spending mix, budget health, savings goals, and quick insights.
2. **Accounts** — account CRUD, derived balances, archive, transfers between accounts.
3. **Transactions** — explicit income/expense creation, edit/delete, search, category/type/date filtering, sorting, and client-side paginated history.
4. **Budgets** — category limits, live spend, remaining/over-limit states, edit/delete.
5. **Goals** — CRUD, direct contributions, completion states, aggregate funding.
6. **Reports** — read-only views over the loaded dashboard data.
7. **Settings** — account summary, Firebase-backed password change, CSV portability, demo/reset controls, finance-data clearing, and account deletion.

## Data portability

CSV export is generated client-side from the loaded transaction history. A full JSON backup comes from `GET /api/export`.

CSV import supports quoted fields, escaped quotes, CRLF/LF line endings, optional notes, and required headers. The frontend converts the file to typed JSON and the server performs authoritative validation before persistence.

## UI system

Ledgerly exposes five persistent themes:

- Midnight — default navy/blue
- Emerald
- Violet
- Amber
- Light

The theme layer changes surfaces and accent colors while keeping semantic income, expense, warning, and destructive states understandable. The layout moves from sticky desktop sidebar to bounded native-width mobile navigation. Forms include visible labels, focus-visible states, disabled states, and semantic/ARIA annotations where useful.

## Deployment architecture

Render hosts:

- PostgreSQL database
- Flask/Gunicorn API service
- `/api/health` HTTP health check
- React/Vite static frontend with SPA rewrite

Firebase hosts/manages identity.

Environment-specific values include:

- API `CLIENT_ORIGIN` = deployed frontend origin
- Frontend `VITE_API_URL` = deployed API URL plus `/api`
- Firebase Web configuration on the static frontend
- Firebase project id + protected service-account JSON on the API

The deployed frontend domain must be included in Firebase Authentication's authorized domains. Privileged service-account credentials are supplied only through the backend deployment environment and are never committed.

## Data flow

1. The SPA signs in with Firebase and, per request, calls `getIdToken()` and sends `Authorization: Bearer <token>`.
2. `firebase_required()` (`server/app/firebase_auth.py`) calls `verify_id_token(token, check_revoked=True)`, maps the claims to a `User`, and stores it on `flask.g`. Any failure returns 401 with a generic message.
3. The view reads `current_user_id()` and filters every query by that internal id. Request bodies cannot supply a user id.
4. `GET /api/dashboard` loads the user's accounts, all transactions, budgets and goals and computes balances, monthly KPIs, category spend, budget status, six-month trend and insights in Python, using `Decimal`. Writes validate, commit, and return the serialized row; the client then refetches the dashboard.

## Authentication and authorization details

- Identity linking (`_ledgerly_user_for_claims`): look up by `firebase_uid`; otherwise an existing email is linked only if the token's email is verified and the row has no different UID. This check is independent of `FIREBASE_REQUIRE_VERIFIED_EMAIL`, so relaxing that flag for development cannot hand an unverified identity another person's data. Parallel first requests that race to insert the user are resolved by catching `IntegrityError`, rolling back and re-reading.
- Tests authenticate with `Bearer test-firebase:<uid>:<email>`, honoured only when `app.testing` is true (`_test_claims`). Production never sets `TESTING`; a deployment that did would accept forged tokens. This is a deliberate trade-off for fast tests without the Firebase emulator.
- Ownership is enforced by query (`filter_by(id=..., user_id=uid).first_or_404()`), so another user's id yields 404, not 403.

## Security decisions

- Firebase owns credentials; the API stores a random unusable `password_hash` only to satisfy a legacy NOT NULL column.
- CORS is limited to `CLIENT_ORIGIN` with no cookies (`supports_credentials=False`), so CSRF does not apply to bearer-token calls.
- Defensive headers (`nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Permissions-Policy`) and `Cache-Control: no-store` on JSON; 2 MiB request cap (413 handler); `ProxyFix` for one proxy hop.
- Every SQL value goes through SQLAlchemy bound parameters; the only raw SQL is the fixed-string schema upgrade code.
- CI runs `npm audit --audit-level=high` on the client. `@grpc/grpc-js` is pinned via `overrides` because Firebase's Firestore package declares a vulnerable range; it is not used by the browser bundle.
- Not implemented: API rate limiting, audit log, row-level security.

## Testing strategy

`cd server && python -m pytest -q` runs 43 tests against in-memory SQLite with the test-token path above, so no Firebase project or network is needed. Groups: ownership and isolation across all resources (`test_account_import.py`), identity creation/linking/claiming (`test_auth_security.py`, `test_regressions.py`), exact-cent sums, rounding and legacy REAL rows (`test_money.py`), JSON numbers (`test_json_numbers.py`), accounts/transfers/partial import (`test_accounts_transfers.py`), input limits (`test_transactions.py`, `test_budgets_goals.py`), and additive schema upgrade (`test_schema_upgrade.py`). Gaps: the PostgreSQL-only `ensure_money_schema` path and the IntegrityError race branch have no automated test; SQLite is the only test database; there is no frontend test suite, only `tsc` and the production build, plus an optional emulator smoke script (`client/e2e/local-smoke.mjs`).

## CI

`.github/workflows/ci.yml` on push to `main` and pull requests: a client job (`npm ci`, `npm audit --audit-level=high`, `npm run typecheck`, `npm run build`, Node 24) and a server job (`pytest -q` on Python 3.12 and 3.14).

## Known limitations

- `/dashboard`, `/transactions` and `/export` return every row; pagination on the Transactions page is client-side only. Fine for personal scale, not for heavy importers.
- Dashboard `unbudgetedSpending` compares categories with exact case, while budget spend uses case-insensitive matching, so a differently-cased category can count as both budgeted and unbudgeted.
- No unique constraint on budget `(user_id, category)`.
- "Current month" uses the server's `date.today()`, not the user's time zone.
- Money is capped at `NUMERIC(12,2)` and 999,999,999.99; single currency.
- No recurring transactions, no bank sync, no frontend tests, no Alembic migrations.

## Future improvements

Not implemented: server-side pagination and SQL aggregates for the dashboard; Alembic migrations; a unique `(user_id, lower(category))` budget index; per-user time zone; a PostgreSQL service in CI to cover the Postgres schema path; API rate limiting; frontend component and end-to-end tests in CI.
