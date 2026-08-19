# Ledgerly

A polished personal-finance dashboard for tracking cash flow, managing category budgets, and building savings goals.

## What it demonstrates

Ledgerly is a portfolio-grade full-stack application built with a React + TypeScript frontend and a Flask API. It demonstrates authenticated API design, relational data modeling, responsive product UI, full CRUD workflows, financial analytics, automated tests, and CI.

## Features

### Financial overview
- Net balance, total income, total expenses, and savings-rate metrics
- Six-month income vs. expense cash-flow visualization
- Spending breakdown by category
- Current-month budget health
- Savings-goal progress and quick financial insights

### Transactions
- Create, edit, and delete transactions
- Income and expense categorization
- Optional notes
- Search across description, category, and notes
- Filter by category and transaction type
- Responsive transaction history

### Budgets
- Create and update monthly category budgets
- Live current-month spend calculation
- Remaining/over-budget amounts
- Visual over-limit states
- Edit and delete controls

### Savings goals
- Create, edit, and delete goals
- Track target and saved amounts
- Add contributions directly to an existing goal
- Completion states and aggregate goal progress

### Platform
- User registration and JWT authentication
- Responsive dark fintech design
- PostgreSQL-ready backend with SQLite fallback for local development
- Pytest API coverage for authentication, transactions, budgets, goals, and demo seeding
- GitHub Actions frontend build + backend test CI

## Stack

**Frontend:** React, TypeScript, Vite, CSS  
**Backend:** Python, Flask, Flask-SQLAlchemy, Flask-JWT-Extended  
**Database:** PostgreSQL in production / SQLite locally  
**Tooling:** GitHub Actions, pytest, npm, Vite

## Local setup

### Backend

```bash
cd server
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

The API runs at `http://localhost:5000`. Health check: `http://localhost:5000/api/health`.

### Frontend

Open another terminal:

```bash
cd client
npm install
npm run dev
```

The app runs at `http://localhost:5173`.

The default local API URL is `http://localhost:5000/api`. Copy `.env.example` to `.env` if you need to override environment values.

## Demo flow

Register a fresh account and choose **Load realistic demo data** from the Overview page. Ledgerly seeds six months of sample cash flow plus current budgets and savings goals, making the analytics and management flows immediately testable.

## API overview

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/dashboard`
- `GET|POST /api/transactions`
- `PATCH|DELETE /api/transactions/:id`
- `GET|POST /api/budgets`
- `PATCH|DELETE /api/budgets/:id`
- `GET|POST /api/goals`
- `PATCH|DELETE /api/goals/:id`
- `POST /api/goals/:id/contribute`
- `POST /api/demo/seed`
- `GET /api/health`

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for design details.

## Status

Ledgerly is a complete portfolio MVP. The core finance workflows are implemented end-to-end and the architecture leaves room for future integrations such as recurring transactions, CSV import/export, bank aggregation, and richer reporting without changing the core domain model.
