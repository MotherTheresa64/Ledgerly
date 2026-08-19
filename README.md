# Ledgerly

Ledgerly is a production-minded full-stack personal-finance application for tracking cash flow, managing monthly budgets, and building savings goals through a polished responsive dashboard.

## Consumer-ready v1 feature set

### Authentication and account lifecycle
- User registration with verified-email activation
- Resend verification flow with expiring, one-time verification links
- Resend-verification action for accounts that have not activated yet
- Non-enumerating forgot-password flow
- Expiring, one-time password-reset links
- Strong password policy and Werkzeug password hashing
- Signed JWT access tokens with configurable expiry
- Session revocation after password changes/resets through per-user auth versioning
- Account profile summary and verification status
- Password-confirmed permanent account deletion
- Per-IP authentication rate limiting
- Strict user ownership checks on every protected finance resource

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

### Appearance and responsive UX
- Desktop, tablet, and native-width mobile layouts
- Mobile navigation that does not require pinch-zooming
- Persistent theme preference stored locally in the browser
- Midnight, Emerald, Violet, Amber, and Light themes
- Semantic income/expense colors remain distinct from the chosen accent theme
- Keyboard-visible focus states and semantic form labels
- Loading, empty, error, success, over-budget, completed-goal, and expired-session states

### Data controls
- Export transaction history to CSV
- Import transaction history from CSV
- Clear all finance data without deleting the account
- Replace current data with a fresh demo dataset
- Permanently delete the account and all associated data

## Tech stack

**Frontend:** React 18, TypeScript, Vite, CSS  
**Backend:** Python, Flask, Flask-SQLAlchemy, Flask-JWT-Extended  
**Database:** PostgreSQL in production / SQLite locally  
**Transactional email:** Resend  
**Testing:** pytest  
**DevOps:** GitHub Actions, Dependabot, Render

## Repository structure

```text
Ledgerly/
├── client/
│   └── src/
│       ├── App.tsx
│       ├── AuthScreen.tsx
│       ├── ThemeSwitcher.tsx
│       ├── api.ts
│       ├── styles.css
│       ├── consumer.css
│       ├── themes.css
│       └── types.ts
├── server/
│   ├── app/
│   │   ├── models.py
│   │   ├── routes.py
│   │   ├── email_service.py
│   │   ├── rate_limit.py
│   │   └── config.py
│   └── tests/
├── docs/
│   ├── ARCHITECTURE.md
│   └── CONSUMER_READINESS.md
├── SECURITY.md
├── render.yaml
└── .github/workflows/ci.yml
```

## Local development

### Backend

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

The API runs at `http://localhost:5000`, with health at `http://localhost:5000/api/health`.

### Frontend

```bash
cd client
npm install
npm run dev
```

The frontend runs at `http://localhost:5173` and defaults to `http://localhost:5000/api` locally.

## Production environment

Server:

```text
SECRET_KEY=<long random value>
JWT_SECRET_KEY=<different long random value>
JWT_ACCESS_TOKEN_HOURS=12
DATABASE_URL=<PostgreSQL URL>
CLIENT_ORIGIN=<frontend origin>
PUBLIC_APP_URL=<frontend origin>
RESEND_API_KEY=<Resend API key>
EMAIL_FROM=Ledgerly <no-reply@verified-sending-domain>
EMAIL_VERIFICATION_REQUIRED=true
```

Client:

```text
VITE_API_URL=<API origin>/api
```

`RESEND_API_KEY` and all other production secrets belong only in the deployment environment. Sending verification/recovery mail to arbitrary public users requires a verified sending domain at the transactional-email provider.

## Quality gates

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

GitHub Actions runs the same checks on pull requests. Backend tests cover both Python 3.12 and Python 3.14.

## CSV format

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

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/CONSUMER_READINESS.md`](docs/CONSUMER_READINESS.md), and [`SECURITY.md`](SECURITY.md) for implementation and deployment details.

## Deployment

`render.yaml` defines the Render deployment: PostgreSQL, the Flask/Gunicorn API, and the React static site. Configure the synced deployment variables above, then allow Render to rebuild from `main`.

## Status

Ledgerly's application code covers the intended consumer v1 scope: verified account lifecycle, password recovery, user-scoped finance CRUD, analytics, budgets, goals, data portability, destructive-data controls, responsive UI, persistent themes, automated security regression tests, CI, and deployment configuration.

A public production instance must additionally provide a verified transactional-email sender domain so verification and password-recovery messages can be delivered to arbitrary users. This is deployment infrastructure rather than an application-code gap.
