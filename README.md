# Ledgerly

A modern personal finance and budgeting platform built to make spending, budgets, goals, and cash flow easy to understand at a glance.

## What it demonstrates

Ledgerly is a portfolio-grade full-stack application built with a React + TypeScript frontend and a Flask API. It demonstrates authenticated API design, relational data modeling, responsive dashboard UI, CRUD workflows, analytics-style summaries, automated tests, and CI.

## Features

- User registration and JWT authentication
- Financial overview with balance, income, expenses, and savings rate
- Transaction creation, filtering, categorization, and deletion
- Monthly category budgets with live progress indicators
- Savings goals with target/progress tracking
- Recent-activity dashboard
- Responsive dark fintech UI
- PostgreSQL-ready backend with SQLite fallback for local development
- Pytest API tests and GitHub Actions CI

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
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

The API runs at `http://localhost:5000`.

### Frontend

```bash
cd client
npm install
npm run dev
```

The app runs at `http://localhost:5173`.

The default local API URL is `http://localhost:5000/api`. Copy `.env.example` to `.env` if you want to override environment values.

## Demo flow

Register an account, then use **Load demo data** from the dashboard to populate a realistic month of transactions, budgets, and savings goals.

## API overview

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/dashboard`
- `GET|POST /api/transactions`
- `DELETE /api/transactions/:id`
- `GET|POST /api/budgets`
- `GET|POST /api/goals`
- `POST /api/demo/seed`
- `GET /api/health`

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for design details.

## Status

Feature-complete MVP. The repository is intentionally structured so additional integrations such as bank aggregation, recurring transactions, CSV import/export, and richer reporting can be added without rewriting the core domain model.
