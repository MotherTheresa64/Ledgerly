# Ledgerly

Ledgerly is a full-stack personal-finance application for tracking cash flow, managing monthly budgets, and building savings goals through a polished responsive dashboard.

## Why this project exists

Ledgerly was built as a production-minded application rather than a single-screen CRUD demo. It demonstrates full-stack product design, authenticated API architecture, user-scoped relational data, analytics, account recovery, transactional email, destructive-action safety, data portability, test coverage, CI, and deployment configuration.

## v1.0 feature set

### Authentication and account management
- User registration and login
- Password hashing with Werkzeug
- Email verification for new production accounts
- Resend-verification flow with cooldowns
- Forgot-password and one-time password-reset links
- Signed, expiring email verification and reset tokens
- Password policy requiring 10–128 characters with a letter and a number
- Signed JWT access tokens with configurable expiry
- Server-side session revocation after password changes or resets
- Durable per-IP rate limits on public authentication endpoints
- Account profile and email-verification status
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
- Native-width desktop, tablet, and mobile layouts without requiring browser zoom adjustments
- Keyboard-visible focus states and semantic form labels
- Loading, empty, error, success, over-budget, completed-goal, verification, recovery, and expired-session states
- Confirmation flows for destructive operations
- Server-side input validation and request-size limits
- Authentication endpoint rate limiting
- API security headers and no-store responses
- PostgreSQL production configuration with SQLite local fallback
- Render Blueprint for frontend, API, health checks, and PostgreSQL
- Dependency update automation with Dependabot
- Security documentation in [`SECURITY.md`](SECURITY.md)

## Tech stack

**Frontend:** React 18, TypeScript, Vite, CSS  
**Backend:** Python, Flask, Flask-SQLAlchemy, Flask-JWT-Extended  
**Database:** PostgreSQL in production / SQLite locally  
**Email:** Resend transactional email API  
**Testing:** pytest  
**DevOps:** GitHub Actions, Dependabot, Render

## Repository structure

```text
Ledgerly/
├── client/
│   └── src/
│       ├── App.tsx          # Finance application and product workflows
│       ├── AuthScreen.tsx   # Sign-in, registration, verification, recovery
│       ├── api.ts           # Typed API client
│       ├── styles.css       # Base responsive design system
│       ├── consumer.css     # Consumer/mobile responsive hardening
│       └── types.ts         # Shared frontend domain types
├── server/
│   ├── app/
│   │   ├── models.py        # Users, rate limits, transactions, budgets, goals
│   │   ├── routes.py        # Auth and finance REST API
│   │   ├── email_service.py # Transactional email delivery
│   │   ├── rate_limit.py    # Durable auth abuse limits
│   │   └── config.py        # Environment/database/security config
│   └── tests/               # API, auth security, isolation, CRUD, import tests
├── docs/
│   ├── ARCHITECTURE.md
│   └── CONSUMER_READINESS.md
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

For local development without an email provider, set `EMAIL_VERIFICATION_REQUIRED=false`. Production should keep verification enabled.

### 2. Frontend

In another terminal:

```bash
cd client
npm install
npm run dev
```

The frontend runs at `http://localhost:5173` and defaults to `http://localhost:5000/api` for local API requests.

## Environment variables

Never commit production secrets.

Server:

```text
SECRET_KEY=<long random value>
JWT_SECRET_KEY=<different long random value>
JWT_ACCESS_TOKEN_HOURS=12
DATABASE_URL=<PostgreSQL URL in production>
CLIENT_ORIGIN=<frontend origin>
PUBLIC_APP_URL=<frontend public URL>
RESEND_API_KEY=<Resend API key>
EMAIL_FROM=Ledgerly <hello@your-verified-domain.example>
EMAIL_VERIFICATION_REQUIRED=true
```

Client:

```text
VITE_API_URL=<API origin>/api
```

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
POST   /api/auth/verify-email
POST   /api/auth/resend-verification
POST   /api/auth/forgot-password
POST   /api/auth/reset-password
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

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/CONSUMER_READINESS.md`](docs/CONSUMER_READINESS.md), and [`SECURITY.md`](SECURITY.md) for implementation and deployment requirements.

## Deployment

`render.yaml` defines the Render topology:

1. PostgreSQL database
2. Flask/Gunicorn API service with `/api/health` health checks
3. React static frontend

Production requires the frontend/API origins plus a verified transactional-email sender. Email verification should remain enabled for public use.

Large external integrations such as bank aggregation are intentionally outside the v1.0 scope because they require third-party financial credentials. Ledgerly's core finance workflows are fully usable without connecting a bank account.
