# Ledgerly

Ledgerly is a full-stack personal-finance application for understanding cash flow, tracking financial accounts and transactions, managing monthly budgets, and building savings goals through a responsive dashboard.

It is intentionally a finance tracker rather than a bank. Ledgerly does not claim bank connectivity or fabricate account synchronization: users can work with their own manual data, import transactions, or load clearly fictional demo data.

## Features

### Financial overview
- Tracked balance across active accounts plus unassigned manual transactions
- Current-month income, expenses, net cash flow, and savings rate
- Six-month income-vs-expense trend
- Spending breakdown by category
- Monthly budget health and over-budget states
- Savings-goal progress
- Derived, factual insights based only on the user's Ledgerly data
- Empty, loading, success, error, and populated demo states

### Accounts and transfers
- Checking, savings, cash, credit, loan/debt, investment-tracking, and custom accounts
- Opening balances and live balances derived from account activity
- Archive/include-in-total controls
- Guarded account deletion when transactions still reference an account
- Paired transfers between active accounts without inflating income or expenses

### Transactions
- Create, edit, and delete income/expense transactions
- Explicit transaction type so normal entry never requires users to reason about signed storage values
- Account assignment, category, subcategory, tags, notes, and local calendar dates
- Search, filters, sorting, and pagination
- CSV import/export
- Duplicate detection and optional partial import of valid rows
- Paired-transfer deletion protection

### Budgets and goals
- Monthly category budgets derived from actual expense transactions
- Remaining amount, percent used, approaching-limit, and over-limit states
- Percentages remain numerically correct above 100%; the visual progress bar is intentionally capped at its container width
- Savings goals with targets, saved amounts, target dates, notes, contributions, and completed states

### Authentication and privacy
- Firebase Authentication for email/password identity
- Email verification and Firebase-managed password reset
- Firebase ID tokens verified server-side with the Firebase Admin SDK
- Server-side ownership checks on every protected finance resource
- Firebase reauthentication before password changes and permanent account deletion
- Bearer tokens are not copied into Ledgerly `localStorage`; the UI stores only a non-sensitive session marker while API requests obtain the active Firebase user's current token
- Financial API JSON is marked `no-store`

### Responsive UX
- Desktop, laptop, tablet, and phone layouts
- Mobile navigation designed for touch rather than horizontal desktop navigation
- Mobile-friendly transaction representation and controls
- Persistent appearance themes
- Visible keyboard focus states, semantic labels, accessible status/error messaging, and reduced-motion support where animation is used

## Financial correctness

Money is stored and calculated as **integer cents** in canonical `BIGINT` columns:

```text
financial_account.opening_balance_cents
transaction.amount_cents
budget.limit_cents
goal.target_cents
goal.saved_cents
```

The API parses monetary input through Python `Decimal`, rejects `NaN`, `Infinity`, fractional cents, zero where not meaningful, and values above `$999,999,999.99`, then converts to exact integer cents. Aggregations, balances, budgets, percentages, transfers, imports, and dashboard calculations operate on those integer values.

Legacy floating-point columns remain temporarily as synchronized compatibility mirrors so an existing Ledgerly database can upgrade in place. Application startup performs an additive schema migration and backfills cent columns from legacy values. New application logic does not use the float mirrors for financial calculations.

## Date correctness

Transaction dates are calendar dates (`YYYY-MM-DD`), not UTC timestamps. The browser sends its local calendar date as an `asOf` context for current-period dashboards, budgets, exports, and demo data so month boundaries are based on the user's local day rather than whichever timezone hosts the API.

The API also supports an explicit `?asOf=YYYY-MM-DD` value, which makes month-boundary behavior deterministic and directly testable.

## Tech stack

**Frontend:** React 18, TypeScript, Vite, Firebase Web SDK, CSS  
**Backend:** Python, Flask, Flask-SQLAlchemy, Firebase Admin SDK  
**Database:** PostgreSQL in production; SQLite for local development/tests  
**Identity:** Firebase Authentication  
**Testing:** pytest  
**CI/CD:** GitHub Actions, Dependabot, Render

## Architecture

```text
Browser / React
  │
  ├── Firebase Authentication
  │     └── current Firebase ID token
  │
  └── HTTPS JSON API
          │
          ▼
      Flask API
          │ verifies Firebase token + resolves Ledgerly user
          │ validates domain input
          │ performs exact-cent finance calculations
          ▼
      SQLAlchemy
          │
          ▼
      PostgreSQL / SQLite
```

Firebase is the credential authority. Ledgerly's database is the finance-data source of truth. The backend never trusts a client-supplied Ledgerly user id; authenticated ownership is derived from the verified Firebase identity.

Important backend responsibilities are separated into:
- `firebase_auth.py` — Firebase Admin verification and identity mapping
- `money.py` — exact monetary parsing/conversion/percentage helpers
- `models.py` — persisted domain records and legacy migration mirrors
- `routes.py` — finance API workflows and aggregations
- `__init__.py` — app setup, additive schema upgrades, CORS, safe error handling, request/response security controls

## Repository structure

```text
Ledgerly/
├── client/
│   └── src/
│       ├── App.tsx
│       ├── AuthScreen.tsx
│       ├── api.ts
│       ├── date.ts
│       ├── firebase.ts
│       ├── ThemeSwitcher.tsx
│       ├── types.ts
│       └── *.css / focused UI helpers
├── server/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── firebase_auth.py
│   │   ├── money.py
│   │   ├── models.py
│   │   └── routes.py
│   └── tests/
├── docs/
├── SECURITY.md
├── render.yaml
└── .github/workflows/ci.yml
```

## Getting started

### Prerequisites
- Node.js 24 (matches CI)
- Python 3.12+ (CI covers 3.12 and 3.14)
- A Firebase project with Email/Password Authentication enabled

See [`docs/FIREBASE_SETUP.md`](docs/FIREBASE_SETUP.md) for Firebase setup details.

### 1. Clone

```bash
git clone https://github.com/MotherTheresa64/Ledgerly.git
cd Ledgerly
```

### 2. Backend

```bash
cd server
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Local API: `http://localhost:5000`  
Health check: `http://localhost:5000/api/health`

The local default database is SQLite. Tables and additive compatibility migrations are applied on application startup.

### 3. Frontend

In another terminal:

```bash
cd client
npm install
npm run dev
```

Local frontend: `http://localhost:5173`

## Environment variables

### Backend

```text
SECRET_KEY=<long random value>
DATABASE_URL=<PostgreSQL URL in production; optional locally>
CLIENT_ORIGIN=<allowed frontend origin; comma-separated origins supported>
FIREBASE_PROJECT_ID=<Firebase project id>
FIREBASE_SERVICE_ACCOUNT_JSON=<backend-only service-account JSON>
FIREBASE_REQUIRE_VERIFIED_EMAIL=true
```

The backend can also use `GOOGLE_APPLICATION_CREDENTIALS` / Application Default Credentials instead of embedding service-account JSON in an environment variable. Never expose the service-account credential to the frontend.

### Frontend

```text
VITE_API_URL=<API origin>/api
VITE_FIREBASE_API_KEY=<Firebase Web API key>
VITE_FIREBASE_AUTH_DOMAIN=<project>.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=<Firebase project id>
VITE_FIREBASE_APP_ID=<Firebase web app id>
```

Firebase Web configuration is intentionally browser-visible; it is not the privileged service-account credential.

## Testing and quality gates

Backend:

```bash
cd server
pytest -q
```

The suite covers authentication boundaries, user isolation, account/transfer behavior, imports, transactions, budgets, goals, exact-cent arithmetic, fractional-cent rejection, month boundaries, over-100% budgets, schema migration/backfill, safe missing-resource errors, and security headers.

Frontend:

```bash
cd client
npm install
npm audit --audit-level=high
npm run typecheck
npm run build
```

GitHub Actions runs the frontend gates plus the backend test suite on Python 3.12 and Python 3.14 for every pull request.

## API overview

Firebase provides authentication endpoints. Ledgerly exposes the finance/account-data API:

```text
GET    /api/health
GET    /api/account
DELETE /api/account
GET    /api/accounts
POST   /api/accounts
PATCH  /api/accounts/:id
DELETE /api/accounts/:id
GET    /api/dashboard
GET    /api/transactions
POST   /api/transactions
POST   /api/transactions/import
PATCH  /api/transactions/:id
DELETE /api/transactions/:id
POST   /api/transfers
GET    /api/budgets
POST   /api/budgets
PATCH  /api/budgets/:id
DELETE /api/budgets/:id
GET    /api/goals
POST   /api/goals
PATCH  /api/goals/:id
POST   /api/goals/:id/contribute
DELETE /api/goals/:id
GET    /api/export
DELETE /api/data
POST   /api/demo/seed
POST   /api/demo/reset
```

Protected requests send the current Firebase ID token as `Authorization: Bearer <token>`. The API verifies it, maps the Firebase UID to an internal user, and scopes finance operations to that user.

## Key engineering decisions

- **Exact integer cents:** avoids binary floating-point accumulation errors in financial calculations.
- **Additive migration:** existing deployments can backfill cents without a destructive database reset.
- **Paired transfer records:** transfers move value between accounts while remaining excluded from income/expense analytics.
- **Server-side ownership:** frontend filtering is never treated as authorization.
- **Local `asOf` context:** current-month calculations stay correct across browser/server timezone boundaries and are deterministic in tests.
- **Grouped account/budget aggregation:** avoids per-account/per-budget query loops on dashboard reads.
- **Managed identity:** Firebase owns credentials while Ledgerly stays focused on financial-domain logic.
- **Safe API failures:** database failures roll back, unexpected exceptions return generic user-safe messages, and request IDs make failures traceable without exposing stack traces.

## Deployment

[`render.yaml`](render.yaml) defines:
- PostgreSQL database
- Gunicorn/Flask API service
- Vite static frontend
- API health check
- SPA route rewrite

For production, configure the backend/frontend environment variables, add the deployed frontend domain to Firebase Authentication's authorized domains, and ensure `CLIENT_ORIGIN` matches the deployed frontend origin.

## Security

See [`SECURITY.md`](SECURITY.md). Do not commit database URLs, Firebase Admin credentials, private keys, passwords, bearer tokens, or real personal financial data.

## Limitations

Ledgerly currently uses manual/demo/CSV financial data; it does not connect to banks or payment networks. That limitation is intentional and represented honestly in the UI/repository rather than simulated as a real banking integration.
