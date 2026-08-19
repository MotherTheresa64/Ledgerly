# Ledgerly architecture

## Overview

Ledgerly is a full-stack monorepo with a React/TypeScript SPA and a Flask REST API:

- `client/` — product UI, client-side interaction state, CSV import/export helpers, and typed API access
- `server/` — authentication, validation, finance-domain persistence, analytics, and account lifecycle APIs
- `server/app/models.py` — relational domain models
- `server/app/routes.py` — user-scoped REST endpoints and derived finance read models
- `server/tests/` — API, security, ownership, account, import, and CRUD tests
- `.github/workflows/ci.yml` — frontend dependency audit/typecheck/build plus backend tests on Python 3.12 and 3.14
- `render.yaml` — PostgreSQL, API, static frontend, and health-check deployment definition

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

This avoids the common dashboard bug where monthly labels display all-time totals.

## API design

### Authentication and account

- Register and login return a signed JWT access token.
- Access token expiry is configured through `JWT_ACCESS_TOKEN_HOURS`.
- `GET /api/account` returns the authenticated user's account summary.
- Password changes require the existing password.
- Account deletion requires password confirmation and removes owned finance records before deleting the user.

### Transactions

- Create, list, update, and delete
- Optional notes
- Atomic validated bulk import (maximum 1,000 rows per request)
- Every item lookup includes the authenticated `user_id`

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

## Authentication behavior

The SPA stores the short-lived access token in local storage and sends it with `Authorization: Bearer <token>`.

The API client centrally detects `401` responses, clears the invalid token, and emits a session-expired event. The top-level application returns the user to authentication with a clear message instead of leaving the dashboard in a broken loading state.

This architecture keeps the backend stateless and easy to deploy independently. The tradeoff and future same-origin/HttpOnly-cookie option are documented in `SECURITY.md`.

## Ownership and authorization

Resource-level authorization is enforced server-side, not trusted to the UI. Transaction, budget, and goal updates/deletes query by both object ID and authenticated user ID. Tests explicitly verify that one user cannot read, edit, or delete another user's records through guessed IDs.

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
5. **Settings** — account summary, password change, CSV portability, demo/reset controls, finance-data clearing, and account deletion.

## Data portability

CSV export is generated client-side from the currently loaded user transaction history, so no additional backend download endpoint is needed.

CSV import supports quoted fields, escaped quotes, CRLF/LF line endings, optional notes, and required headers. The frontend converts the file to typed JSON and the server performs authoritative validation before persistence.

## UI system

Ledgerly uses a restrained dark-fintech visual system:

- Background: `#090D0B`
- Surface: `#111A15`
- Elevated surface: `#16221B`
- Brand green: `#22C55E`
- Positive: `#4ADE80`
- Warning: `#F59E0B`
- Danger: `#EF4444`
- Primary text: `#F4F7F5`
- Secondary text: `#94A39A`

The layout moves from sticky desktop sidebar → horizontal tablet navigation → single-column mobile content. Forms include visible labels, focus-visible states, disabled states, and semantic/ARIA annotations where useful.

## Deployment architecture

The Render Blueprint defines:

- PostgreSQL database
- Flask/Gunicorn web service
- `/api/health` HTTP health check
- React/Vite static frontend with SPA rewrite

Two deployment values remain intentionally environment-specific:

- API `CLIENT_ORIGIN` must equal the deployed frontend origin.
- Frontend `VITE_API_URL` must equal the deployed API URL plus `/api`.

Secrets are generated or supplied in the hosting environment and are never committed.
