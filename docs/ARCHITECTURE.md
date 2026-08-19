# Ledgerly architecture

## Overview

Ledgerly is a full-stack monorepo with a React/TypeScript SPA, Firebase Authentication, a Flask REST API, and PostgreSQL persistence:

- `client/` — product UI, Firebase browser authentication, client-side interaction state, CSV helpers, and typed API access
- Firebase Authentication — registration, login, email verification, password recovery, and credential lifecycle
- `server/` — Firebase ID-token verification, finance-domain validation, persistence, analytics, and account-data APIs
- `server/app/firebase_auth.py` — Firebase Admin verification and Firebase UID → Ledgerly user mapping
- `server/app/models.py` — relational finance-domain models
- `server/app/routes.py` — user-scoped REST endpoints and derived finance read models
- `server/tests/` — API, security, ownership, account, import, and CRUD tests
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

A `User` owns `Transaction`, `Budget`, and `Goal` records.

- `Transaction` stores signed values: positive is income, negative is expense. The normal UI hides this storage detail behind explicit Income / Expense controls.
- `Budget` stores one monthly limit per category. Spent and remaining amounts are derived from current-month expense transactions.
- `Goal` stores a target amount and current saved amount. Contributions are applied through a dedicated authenticated endpoint.

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

- Create/upsert by category
- Update limits
- Delete
- Current-month spent/remaining values are calculated at read time

### Goals

- Create, update, delete
- Direct positive contributions
- Completion is derived from `saved >= target`

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

Mutation payloads are validated on the server for required fields, non-zero transaction amounts, positive budget/goal values, string length limits, and ISO dates.

CSV is parsed in the browser into the same typed transaction payload used by normal creation. The API validates **every** imported row before adding any row to the session. If any row is invalid, the entire import is rejected, providing all-or-nothing behavior.

## Database strategy

`DATABASE_URL` controls persistence:

- local development defaults to SQLite
- production uses PostgreSQL

PostgreSQL connection strings supplied by hosting providers are normalized to the Psycopg SQLAlchemy driver in `config.py`.

## Frontend product areas

1. **Overview** — lifetime balance, monthly KPIs, six-month trend, spending mix, budget health, savings goals, and quick insights.
2. **Transactions** — explicit income/expense creation, edit/delete, search, category/type/date filtering, sorting, and complete history.
3. **Budgets** — category limits, live spend, remaining/over-limit states, edit/delete.
4. **Goals** — CRUD, direct contributions, completion states, aggregate funding.
5. **Settings** — account summary, Firebase-backed password change, CSV portability, demo/reset controls, finance-data clearing, and account deletion.

## Data portability

CSV export is generated client-side from the currently loaded user transaction history, so no additional backend download endpoint is needed.

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
