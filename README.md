# Ledgerly

Ledgerly is a production-minded full-stack personal-finance application for tracking accounts, cash flow, budgets, transfers, savings goals, and portable financial records through a responsive React interface backed by a user-scoped Flask/PostgreSQL API.

## What Ledgerly demonstrates

Ledgerly is intentionally more substantial than a dashboard mockup:

- Firebase Authentication in the browser with Firebase Admin verification on the API
- server-enforced resource ownership for every finance mutation/read
- PostgreSQL production persistence with SQLite support for local/tests
- fixed-precision monetary storage and calculation with SQL `NUMERIC(14,2)` + Python `Decimal`
- explicit asset/liability account semantics
- atomic paired-entry transfers
- monthly budgets and derived dashboard/report calculations
- savings goals with overfunding support
- CSV import plus CSV/JSON export
- explicit destructive-data controls
- durable Alembic/Flask-Migrate schema evolution
- responsive/mobile-specific navigation, transaction pagination, layouts, focus states, touch sizing, and reduced-motion behavior
- backend domain/security regression tests and frontend pagination tests
- GitHub Actions, Dependabot, and Render deployment configuration

## Financial model

### Money precision

Authoritative money is never calculated or stored with binary floating point.

- database: `NUMERIC(14,2)`
- Python: `Decimal`
- rounding: explicit `ROUND_HALF_UP` to cents
- supported magnitude: up to `$999,999,999.99`
- NaN, infinity, and scientific-notation money input are rejected
- JSON numbers are produced only at the API serialization boundary

See [`docs/MONEY_AND_MIGRATIONS.md`](docs/MONEY_AND_MIGRATIONS.md).

### Transaction signs

The UI asks users for a normal positive dollar amount plus **Income** or **Expense**. The backend stores cash-flow direction deliberately:

- income: positive
- expense: negative
- transfer source: negative
- transfer destination: positive

Transfers are excluded from income and expense analytics.

### Account balances and liabilities

Supported account types:

- checking
- savings
- cash
- credit
- loan
- investment
- other

Credit and loan balances are liabilities. Users enter a normal positive opening debt amount; Ledgerly stores that liability as negative internally. A card purchase makes the liability more negative, while a transfer/payment into the card makes the liability less negative.

The dashboard exposes **net worth** separately from liquid/account context. `totalBalance` remains in the API only as a backward-compatible alias for net worth.

### Savings goals

Goal contributions track goal progress; they do **not** claim that money physically moved between financial accounts. Overfunding is preserved rather than silently capped, and the API reports the overfunded amount explicitly.

## Authentication architecture

```text
Browser
  │
  ├── Firebase Authentication
  │     ├── registration / login
  │     ├── email verification
  │     ├── password reset / change
  │     └── recent-login reauthentication
  │
  └── current Firebase ID token
          │ Authorization: Bearer ...
          ▼
      Flask API
          │ verifies token + revocation with Firebase Admin
          │ requires verified email (production default)
          │ maps Firebase UID → internal Ledgerly user
          ▼
      PostgreSQL
          ├── financial accounts
          ├── transactions / transfer pairs
          ├── budgets
          └── goals
```

Firebase owns credentials. Ledgerly never stores or verifies a user's Firebase password on the server. PostgreSQL remains the source of truth for financial data.

A legacy pre-Firebase Ledgerly user may be linked by email only after Firebase has proved that email is verified. An email already mapped to another Firebase UID cannot be claimed.

## Account deletion

Permanent deletion is intentionally a multi-system operation:

1. the browser requires Firebase reauthentication/recent login;
2. the API requires explicit `DELETE` confirmation;
3. Ledgerly financial records are deleted;
4. the backend deletes the authenticated, server-bound Firebase UID;
5. the remaining Ledgerly user metadata row is removed.

If an external Firebase failure occurs after finance-data deletion, the API returns explicit partial-state metadata instead of pretending the entire operation succeeded. No client-supplied Firebase UID is trusted.

## Product areas

### Overview

- net worth and account context
- current-month income, expenses, net cash flow, and savings rate
- six-month income/expense trend
- current-month category spending
- budget health and unbudgeted spending
- savings-goal progress
- financial insights derived from the user's records

### Accounts

- multiple account types
- institution and description metadata
- active/archive state
- include/exclude from totals
- opening/current balance
- liability-aware presentation data
- deletion guardrails for historical transactions and transfers

Accounts involved in historical transfers cannot be hard-deleted; archive them to preserve transfer integrity.

### Transactions and transfers

- create/edit/delete income and expense transactions
- optional account, category, subcategory, tags, notes, and date
- search/filter/sort
- mobile card/row layout instead of a wide desktop table
- compact phone pagination
- paired transfer creation with one stable transfer-group ID
- transfer edits blocked on individual entries
- deleting either side deletes the pair
- database rollback if transfer creation cannot commit both entries

### Budgets

- monthly category limits
- case/whitespace-insensitive category matching
- expense-only spending aggregation
- transfers and income excluded
- healthy / approaching / over states
- remaining or overspent amount

### Savings goals

- create/edit/delete
- target/saved/target date/notes
- contributions
- remaining amount
- percent complete
- overfunding metadata
- explicitly tracking-only unless a real account transfer is separately recorded

### Import/export

The API supports a maximum of 1,000 transaction rows per import request.

- **Atomic mode** is the API default: invalid rows reject the pending import.
- **Partial mode** is an explicit opt-in: valid rows are committed while invalid/duplicate row numbers are reported.
- Ledgerly Settings intentionally uses partial mode and tells the user that invalid/likely duplicate rows are skipped.
- duplicate fingerprints use normalized description/category, exact cent amount, date, and account
- archived accounts cannot receive imports

Transaction CSV export is designed for portability; the full JSON export includes accounts, transactions, budgets, goals, an export schema version, and money-semantics metadata. The full JSON backup is not currently an automatic restore format.

### Demo data

Fictional sample data can be seeded only into an empty account. Demo reset is destructive and requires explicit reset confirmation; sample data is labeled as fictional in the UI/API response.

## Repository structure

```text
Ledgerly/
├── client/
│   └── src/
│       ├── App.tsx
│       ├── AuthScreen.tsx
│       ├── api.ts
│       ├── firebase.ts
│       ├── mobileNavigation.ts
│       ├── transactionPagination.ts
│       ├── financialSemantics.ts
│       ├── readiness.css
│       └── types.ts
├── server/
│   ├── app/
│   │   ├── firebase_auth.py
│   │   ├── money.py
│   │   ├── models.py
│   │   ├── routes.py
│   │   └── config.py
│   ├── migrations/
│   └── tests/
├── docs/
│   ├── ARCHITECTURE.md
│   ├── CONSUMER_READINESS.md
│   ├── FIREBASE_SETUP.md
│   └── MONEY_AND_MIGRATIONS.md
├── SECURITY.md
├── render.yaml
└── .github/workflows/ci.yml
```

## Local development

### Firebase

Create/register a Firebase Web app, enable Email/Password Authentication, and configure backend Admin credentials. See [`docs/FIREBASE_SETUP.md`](docs/FIREBASE_SETUP.md).

### Backend

```bash
cd server
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
flask --app run.py db upgrade
python run.py
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
flask --app run.py db upgrade
python run.py
```

The API runs at `http://localhost:5000`; health is `http://localhost:5000/api/health`.

### Frontend

```bash
cd client
npm install
npm run dev
```

The frontend runs at `http://localhost:5173` and defaults to `http://localhost:5000/api` locally.

## Environment variables

Server:

```text
SECRET_KEY=<long random value>
DATABASE_URL=<PostgreSQL URL in production>
CLIENT_ORIGIN=<frontend origin>
FIREBASE_PROJECT_ID=<Firebase project id>
FIREBASE_SERVICE_ACCOUNT_JSON=<protected service-account JSON>
# or GOOGLE_APPLICATION_CREDENTIALS=<path to protected secret file>
FIREBASE_REQUIRE_VERIFIED_EMAIL=true
```

Client:

```text
VITE_API_URL=<API origin>/api
VITE_FIREBASE_API_KEY=<Firebase Web API key>
VITE_FIREBASE_AUTH_DOMAIN=<project>.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=<Firebase project id>
VITE_FIREBASE_APP_ID=<Firebase web app id>
```

Firebase Web configuration is intentionally browser-visible. Firebase Admin/service-account credentials are privileged backend secrets.

## Quality gates

Backend:

```bash
cd server
pip install -r requirements.txt
pip check
python -m compileall -q app migrations
pytest -q
```

Frontend:

```bash
cd client
npm install
npm audit --audit-level=high
npm test
npm run typecheck
npm run build
```

GitHub Actions runs these gates for pull requests. Backend tests run on Python 3.12 and 3.14.

## API overview

Firebase owns registration/login/password-recovery endpoints. Ledgerly exposes the authenticated finance/account API:

```text
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
GET    /api/health
```

Every protected request uses the current Firebase ID token. Finance resource IDs are always resolved under the authenticated internal Ledgerly user; client-side filtering is never treated as authorization.

## Deployment

`render.yaml` defines PostgreSQL, Flask/Gunicorn, and the React static site. The API runs `flask --app run.py db upgrade` as a pre-deploy command before starting new application code.

Before the first deployment containing the fixed-precision migration, take a PostgreSQL backup/snapshot. The migration changes money columns in place and normalizes positive existing credit/loan opening balances to negative liability values; it does not intentionally drop financial rows.

External setup still required for a live deployment:

- Firebase project / Email+Password provider
- frontend authorized domain in Firebase
- Firebase Admin credentials on the API
- Render environment variables
- a valid `CLIENT_ORIGIN` and frontend `VITE_API_URL`

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/MONEY_AND_MIGRATIONS.md`](docs/MONEY_AND_MIGRATIONS.md), [`docs/FIREBASE_SETUP.md`](docs/FIREBASE_SETUP.md), [`docs/CONSUMER_READINESS.md`](docs/CONSUMER_READINESS.md), and [`SECURITY.md`](SECURITY.md).
