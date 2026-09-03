# Ledgerly architecture

## Overview

Ledgerly is a full-stack monorepo with a React/TypeScript SPA, Firebase Authentication, a Flask REST API, and PostgreSQL persistence:

- `client/` — product UI, Firebase browser authentication, typed API access, CSV helpers, themes, and responsive interaction state
- Firebase Authentication — registration, login, email verification, password recovery, and credential lifecycle
- `server/` — Firebase ID-token verification, finance-domain validation, exact-cent calculations, persistence, analytics, and account-data APIs
- `server/app/firebase_auth.py` — Firebase Admin verification and Firebase UID → Ledgerly user mapping
- `server/app/money.py` — authoritative monetary parsing and integer-cent helpers
- `server/app/models.py` — relational finance-domain records and compatibility mirrors for the legacy money schema
- `server/app/routes.py` — user-scoped REST workflows and derived finance read models
- `server/tests/` — API, security, ownership, finance-correctness, migration, account, import, and CRUD tests
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

The Flask API does not receive a user's Firebase login password. A verified Firebase token is mapped to one internal Ledgerly user id, and that internal id is used for all finance ownership queries.

## Browser authentication behavior

Firebase Authentication persistence is owned by the Firebase SDK. Ledgerly keeps only the literal non-sensitive marker `firebase-session` in its historical `ledgerly_token` local-storage key for the top-level UI gate; no Firebase bearer token is copied into Ledgerly storage.

Before every protected request, the API client waits for Firebase auth state and calls `getIdToken()` on the active user. That current token is sent to Flask. If the API responds with `401`, the UI marker is cleared and Ledgerly returns to authentication.

## Identity mapping and migration

`User.firebase_uid` stores the Firebase identity mapping.

On the first authenticated API call:

1. Firebase Admin verifies the bearer token, including revocation checking.
2. Ledgerly reads `uid`, `email`, and `email_verified` from verified claims.
3. If that Firebase UID is already mapped, the Ledgerly user is loaded.
4. Otherwise, a pre-Firebase Ledgerly record with the same verified email can be linked, preserving existing finance history.
5. If no record exists, a new internal user is created.

A second Firebase UID cannot claim an email already mapped to another UID.

The production schema retains a historical non-null `password_hash` column. New Firebase users receive a random unusable placeholder only to satisfy that legacy constraint; it is never used for authentication.

## Domain model

A `User` owns:

- `FinancialAccount` — account metadata, exact opening balance, archive/include-in-total state
- `Transaction` — income, expense, or one side of a paired transfer
- `Budget` — monthly category limit
- `Goal` — target, saved amount, target date, and notes

Analytics are derived from source records rather than persisted as duplicate totals.

### Exact money representation

Canonical finance values are stored in integer cents:

```text
FinancialAccount.opening_balance_cents  BIGINT
Transaction.amount_cents                BIGINT
Budget.limit_cents                      BIGINT
Goal.target_cents                       BIGINT
Goal.saved_cents                        BIGINT
```

Incoming values are parsed with `Decimal`, limited to two decimal places, bounded to `$999,999,999.99`, and converted to cents. Financial calculations operate on integers, preventing binary floating-point drift.

Legacy float columns remain synchronized compatibility mirrors during the migration window. Startup performs additive schema upgrades and backfills cent values so deployed data can migrate without a destructive reset.

### Transaction signs and transfers

Normal income amounts are stored as positive cents and expenses as negative cents. The UI uses explicit Income/Expense controls, so users do not need to enter signed values manually.

A transfer is stored as two transactions sharing one `transfer_group`: a negative source entry and an equal positive destination entry. Transfer records are excluded from income/expense analytics. Deleting one side deletes the pair; editing one side is blocked to preserve invariants.

## Dashboard read model

`GET /api/dashboard` returns the main product read model in one authenticated request:

- tracked balance
- current-month income, expenses, net cash flow, and savings rate
- account balances and transaction counts
- current-month category spending
- current-month budget progress and remaining amounts
- transaction history
- savings goals
- six-month income / expense / net trend
- monthly planning summary
- factual derived insights

Account activity and budget spending are grouped in aggregate queries rather than issuing a query per account/budget.

## Calendar-date semantics

Transactions use calendar dates (`YYYY-MM-DD`) instead of timestamps. Current-period endpoints accept `?asOf=YYYY-MM-DD`.

The browser supplies its local date when reading current-period dashboard/export data or mutating budgets/demo data. This avoids a server in another timezone moving the user into the next/previous month near midnight and also makes month-boundary behavior deterministic in tests.

If `asOf` is omitted, the API falls back to its local current date for backwards compatibility.

## API design

Firebase owns authentication endpoints; Flask owns finance/account APIs.

### Account data

- `GET /api/account` — mapped Ledgerly account summary
- `DELETE /api/account` — delete Ledgerly account/finance records after client-side Firebase reauthentication
- Password changes happen through Firebase after reauthentication

### Financial accounts

- List/create/update
- Archive/include-in-total state
- Delete empty accounts
- Accounts with transactions require explicit detach semantics rather than silently orphaning records

### Transactions

- Create/list/update/delete
- Account/category/subcategory/tags/notes/date fields
- Search/filter/sort are presentation concerns in the SPA
- Bulk import is capped at 1,000 rows
- Atomic import rejects the full batch on invalid rows
- Optional partial import skips invalid and duplicate rows and reports their row numbers

### Budgets

- Create/upsert case-insensitively by category
- Update/delete
- Current-month spent, remaining, percent-used, and status are derived from exact expense cents
- Percent used can exceed 100 even though the visual bar is capped to its container

### Goals

- Create/update/delete
- Positive contributions through a dedicated endpoint
- Completion and remaining amount are derived from exact cents
- Contribution overflow is rejected before storage

### Data tools

- Export the authenticated user's structured Ledgerly data
- Clear finance data while keeping the account
- Seed a completely empty account with fictional sample data
- Reset an account to the sample dataset for evaluation

## Authorization

Authorization is server-side. The client never supplies a trusted Ledgerly `user_id`.

Individual resource mutations query by both resource id and the authenticated internal user id. Tests verify cross-user read/mutation isolation for transactions, budgets, goals, accounts, and clear-data behavior.

## Validation and failure handling

Server validation covers:

- required fields and length limits
- exact finite monetary values
- positive/zero constraints by domain operation
- supported account and transaction types
- local calendar-date format
- account ownership and archive state
- transfer invariants
- duplicate import fingerprints
- import row limits

Database failures roll back the active SQLAlchemy transaction. HTTP errors and unexpected failures return predictable JSON rather than Flask HTML or stack traces. API responses include `X-Request-ID` so a production failure can be correlated with server logs without exposing finance payloads to the client.

## Database strategy

`DATABASE_URL` controls persistence:

- local development defaults to SQLite
- production uses PostgreSQL

Provider-style `postgres://` / `postgresql://` URLs are normalized to the Psycopg SQLAlchemy driver in `config.py`.

`db.create_all()` establishes a fresh schema; additive startup migration code upgrades known historical Ledgerly columns in-place. Finance migration behavior is covered by tests that recreate the legacy float-only table shapes and verify exact cent backfills.

## Frontend product areas

1. **Overview** — balance, monthly KPIs, six-month trend, spending mix, budget health, goals, and insights.
2. **Accounts** — financial account CRUD, balances, include/archive controls, and account lifecycle safeguards.
3. **Transactions** — income/expense/transfer entry, edit/delete, import, search/filter/sort, and history pagination.
4. **Budgets** — category limits, live spend, remaining/over-limit states, edit/delete.
5. **Goals** — CRUD, direct contributions, completion states, aggregate funding.
6. **Reports** — historical finance context derived from the loaded dataset.
7. **Settings** — account summary, Firebase-backed password change, data portability, demo/reset tools, clear-data, and account deletion.

## Data portability

Structured export comes from `GET /api/export`. CSV-oriented UI workflows transform transaction data for human portability while server-side import remains authoritative for validation and ownership.

## UI system

Ledgerly provides persistent visual themes and a responsive layout that changes from a desktop sidebar to touch-oriented mobile navigation. Forms use visible labels, disabled/busy states, focus-visible styling, semantic status/error messaging, and reduced-motion behavior where motion is present.

The mobile layout is treated as its own interaction surface rather than a shrunken desktop table: transactions, forms, filters, charts, and navigation are constrained for narrow viewports and touch targets.

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
- Firebase project id + protected Firebase Admin credentials on the API

The deployed frontend domain must be included in Firebase Authentication's authorized domains. Privileged credentials are backend-only and never committed.
