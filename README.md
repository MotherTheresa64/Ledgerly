# Ledgerly

Ledgerly is a complete full-stack personal-finance application for tracking cash flow, managing monthly budgets, and building savings goals through a polished responsive dashboard.

## Why this project exists

Ledgerly was built as a production-minded portfolio application rather than a single-screen CRUD demo. It demonstrates full-stack product design, authenticated API architecture, user-scoped relational data, analytics, destructive-action safety, data portability, test coverage, CI, and deployment configuration.

## v1.0 feature set

### Authentication and account management
- User registration and login
- Password hashing with Werkzeug
- Signed JWT access tokens with configurable expiry
- Automatic expired-session recovery in the client
- Account profile summary
- Authenticated password changes
- Password-confirmed account deletion
- Strict user ownership checks on every protected resource

### Financial overview
- Lifetime net balance
- Current-month income, expenses, and savings rate
- Six-month income vs. expense cash-flow visualization
- Current-month spending breakdown by category
- Current-month budget health
- Savings-goal progress
- Quick financial insights
- Realistic six-month demo dataset for evaluation

### Transactions
- Create, edit, and delete transactions
- Explicit Income / Expense selection so users never need to enter negative values manually
- Controlled categories and optional notes
- Search across description, category, and notes
- Filter by category, type, and date range
- Sort by date or transaction magnitude
- CSV export
- Validated, atomic CSV import of up to 1,000 transactions at a time

### Budgets
- Create category budgets
- Update and delete budgets
- Live current-month spend calculations
- Remaining and over-budget amounts
- Clear visual over-limit states

### Savings goals
- Create, edit, and delete savings goals
- Track target and saved amounts
- Add contributions directly to active goals
- Completion states and aggregate progress

### Data controls
- Export transaction history to CSV
- Import transaction history from CSV
- Clear all finance data without deleting the account
- Replace current data with a fresh demo dataset
- Permanently delete the account and all associated data

### Product quality
- Responsive desktop, tablet, and mobile layouts
- Keyboard-visible focus states and semantic form labels
- Loading, empty, error, success, over-budget, completed-goal, and expired-session states
- Confirmation flows for destructive operations
- Server-side input validation
- PostgreSQL production configuration with SQLite local fallback
- Render Blueprint for frontend, API, health checks, and PostgreSQL
- Dependency update automation with Dependabot
- Security documentation in [`SECURITY.md`](SECURITY.md)

## Tech stack

**Frontend:** React 18, TypeScript, Vite 8, CSS  
**Backend:** Python, Flask, Flask-SQLAlchemy, Flask-JWT-Extended  
**Database:** PostgreSQL in production / SQLite locally  
**Testing:** pytest  
**DevOps:** GitHub Actions, Dependabot, Render Blueprint

## Repository structure

```text
Ledgerly/
├── client/                  # React + TypeScript SPA
│   └── src/
│       ├── App.tsx          # Application UI and product workflows
│       ├── api.ts           # Typed API client
│       ├── styles.css       # Responsive design system
│       └── types.ts         # Shared frontend domain types
├── server/
│   ├── app/
│   │   ├── models.py        # User, Transaction, Budget, Goal models
│   │   ├── routes.py        # Authenticated REST API
│   │   └── config.py        # Environment/database/security config
│   └── tests/               # API, security, isolation, CRUD, import tests
├── docs/ARCHITECTURE.md
├── SECURITY.md
├── render.yaml
└── .github/workflows/ci.yml
```

## Local development

### 1. Backend

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

The API runs at `http://localhost:5000`. The health endpoint is `http://localhost:5000/api/health`.

### 2. Frontend

In another terminal:

```bash
cd client
npm install
npm run dev
```

The frontend runs at `http://localhost:5173` and defaults to `http://localhost:5000/api` for local API requests.

## Environment variables

Copy `.env.example` values into the appropriate deployment environment.

Server:

```text
SECRET_KEY=<long random value>
JWT_SECRET_KEY=<different long random value>
JWT_ACCESS_TOKEN_HOURS=12
DATABASE_URL=<PostgreSQL URL in production>
CLIENT_ORIGIN=<frontend origin>
```

Client:

```text
VITE_API_URL=<API origin>/api
```

Never commit production secrets.

## Test and release checks

Backend:

```bash
cd server
pytest
```

Frontend:

```bash
cd client
npm install
npm audit --audit-level=high
npm run typecheck
npm run build
```

GitHub Actions performs the same quality gates on pull requests. Backend tests run against Python 3.12 and 3.14.

## CSV format

Ledgerly exports and imports the same transaction schema:

```csv
description,amount,category,date,notes
Paycheck,3200,Income,2026-08-18,Primary income
Groceries,-245.50,Food & Dining,2026-08-18,Weekly groceries
```

Imported amounts use the signed storage representation: positive numbers are income and negative numbers are expenses. The normal transaction form hides that implementation detail behind explicit Income / Expense controls.

## API overview

```text
POST   /api/auth/register
POST   /api/auth/login
GET    /api/account
PATCH  /api/account/password
DELETE /api/account
GET    /api/dashboard
GET    /api/transactions
POST   /api/transactions
POST   /api/transactions/import
PATCH  /api/transactions/:id
DELETE /api/transactions/:id
GET    /api/budgets
POST   /api/budgets
PATCH  /api/budgets/:id
DELETE /api/budgets/:id
GET    /api/goals
POST   /api/goals
PATCH  /api/goals/:id
POST   /api/goals/:id/contribute
DELETE /api/goals/:id
DELETE /api/data
POST   /api/demo/seed
POST   /api/demo/reset
GET    /api/health
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for implementation decisions and [`SECURITY.md`](SECURITY.md) for security assumptions and deployment requirements.

## Deployment

`render.yaml` defines the complete Render deployment:

1. PostgreSQL database
2. Flask/Gunicorn API service with `/api/health` health checks
3. React static frontend

When creating the Blueprint, set:

- API `CLIENT_ORIGIN` to the deployed Ledgerly frontend origin.
- Frontend `VITE_API_URL` to the deployed API URL plus `/api`.

Render will then rebuild affected services from the repository on subsequent updates.

## Status

**Ledgerly v1.0 is feature-complete.** The application implements the entire intended portfolio product scope end-to-end: authentication, account lifecycle, finance CRUD, analytics, budgets, goals, search/filter/sort, import/export, destructive-data controls, responsive UI, automated tests, security documentation, dependency maintenance, CI, and production deployment configuration.

Large external integrations such as bank aggregation are intentionally outside the v1.0 product scope because they require third-party financial credentials and do not change the core full-stack architecture demonstrated here.
