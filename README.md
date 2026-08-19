# Ledgerly

Ledgerly is a production-minded full-stack personal-finance application for tracking cash flow, managing monthly budgets, and building savings goals through a polished responsive dashboard.

## Consumer-ready v1 feature set

### Authentication and account lifecycle
- Firebase Authentication for email/password registration and login
- Firebase-managed email verification and password recovery
- Firebase password policy and account security controls
- Firebase ID tokens verified by the Flask API before protected finance data is accessed
- Automatic Firebase UID mapping to Ledgerly's PostgreSQL user records
- Safe migration path for pre-Firebase Ledgerly accounts by verified email
- Firebase reauthentication before password changes and permanent account deletion
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
- Loading, empty, error, success, over-budget, and completed-goal states

### Data controls
- Export transaction history to CSV
- Import transaction history from CSV
- Clear all finance data without deleting the account
- Replace current data with a fresh demo dataset
- Permanently delete the Ledgerly account data and Firebase user

## Tech stack

**Frontend:** React 18, TypeScript, Vite, Firebase Web SDK, CSS  
**Backend:** Python, Flask, Flask-SQLAlchemy, Firebase Admin SDK  
**Database:** PostgreSQL in production / SQLite locally  
**Identity:** Firebase Authentication  
**Testing:** pytest  
**DevOps:** GitHub Actions, Dependabot, Render

## Authentication architecture

```text
Browser
  │
  ├── Firebase Authentication
  │     ├── registration / login
  │     ├── email verification
  │     └── password reset
  │
  └── Firebase ID token
          │
          ▼
      Flask API on Render
          │ verifies token with Firebase Admin
          │ maps Firebase UID → Ledgerly user
          ▼
      PostgreSQL
          ├── transactions
          ├── budgets
          └── goals
```

Firebase owns credentials. Ledgerly never receives or stores a user's login password on the server. PostgreSQL remains the source of truth for financial data.

## Repository structure

```text
Ledgerly/
├── client/
│   └── src/
│       ├── App.tsx
│       ├── AuthScreen.tsx
│       ├── firebase.ts
│       ├── ThemeSwitcher.tsx
│       ├── api.ts
│       ├── styles.css
│       ├── consumer.css
│       ├── themes.css
│       └── types.ts
├── server/
│   ├── app/
│   │   ├── firebase_auth.py
│   │   ├── models.py
│   │   ├── routes.py
│   │   └── config.py
│   └── tests/
├── docs/
│   ├── ARCHITECTURE.md
│   ├── CONSUMER_READINESS.md
│   └── FIREBASE_SETUP.md
├── SECURITY.md
├── render.yaml
└── .github/workflows/ci.yml
```

## Local development

### 1. Firebase

Create a Firebase project, register a Web app, enable Email/Password Authentication, and download a service-account key for local backend development. See [`docs/FIREBASE_SETUP.md`](docs/FIREBASE_SETUP.md).

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

The API runs at `http://localhost:5000`, with health at `http://localhost:5000/api/health`.

### 3. Frontend

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
FIREBASE_SERVICE_ACCOUNT_JSON=<single-line service-account JSON>
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

The Firebase Web configuration is expected to be present in the browser application. The service-account JSON is privileged and belongs only in the backend deployment environment.

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

GitHub Actions runs the same checks on pull requests. Backend tests cover Python 3.12 and Python 3.14.

## CSV format

```csv
description,amount,category,date,notes
Paycheck,3200,Income,2026-08-18,Primary income
Groceries,-245.50,Food & Dining,2026-08-18,Weekly groceries
```

Imported amounts use the signed storage representation: positive numbers are income and negative numbers are expenses. The normal transaction form hides that implementation detail behind explicit Income / Expense controls.

## API overview

Authentication endpoints are provided by Firebase rather than Flask. Ledgerly's backend exposes only the finance/account-data API:

```text
GET    /api/account
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

Every protected request sends the current Firebase ID token in `Authorization: Bearer <token>`. The Flask API verifies that token and resolves it to the corresponding Ledgerly user before querying finance data.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/CONSUMER_READINESS.md`](docs/CONSUMER_READINESS.md), [`docs/FIREBASE_SETUP.md`](docs/FIREBASE_SETUP.md), and [`SECURITY.md`](SECURITY.md) for implementation and deployment details.

## Deployment

`render.yaml` defines PostgreSQL, the Flask/Gunicorn API, and the React static site. Firebase Authentication remains an external managed identity service. Configure the Firebase environment values in Render, add the deployed Ledgerly frontend to Firebase's authorized domains, and allow Render to rebuild from `main`.

## Status

Ledgerly's application code covers the intended consumer v1 scope: managed authentication, email verification, password recovery, user-scoped finance CRUD, analytics, budgets, goals, data portability, destructive-data controls, responsive UI, persistent themes, automated regression tests, CI, and production deployment configuration.
