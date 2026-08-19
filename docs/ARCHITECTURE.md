# Ledgerly architecture

## Overview

Ledgerly uses a small full-stack monorepo:

- `client/` — React + TypeScript single-page application
- `server/` — Flask REST API
- `server/app/models.py` — relational finance domain models
- `server/app/routes.py` — authenticated CRUD and analytics endpoints
- `server/tests/` — API behavior tests
- `.github/workflows/ci.yml` — frontend build + backend test pipeline

## Domain model

A `User` owns `Transaction`, `Budget`, and `Goal` records.

- `Transaction` stores signed values: income is positive and expenses are negative. Each record has a description, category, date, and optional notes.
- `Budget` defines a monthly spending limit for one category. Current spend is calculated from matching negative transactions in the active calendar month rather than duplicated into the budget table.
- `Goal` stores a target and current saved amount. Contributions update saved progress through a dedicated endpoint.

This keeps persistent data small and derives dashboard analytics from source records.

## Dashboard aggregation

`GET /api/dashboard` returns the product's read model in one request:

- balance, income, expenses, and savings rate
- spending totals grouped by category
- current-month budget progress and remaining amount
- goals
- transaction history
- six-month income/expense/net trend data

The six-month trend is derived server-side so the client can focus on presentation rather than duplicating finance calculations.

## API design

Authenticated resources support the operations expected by the interface:

- Transactions: create, update, list, delete
- Budgets: create/upsert, update limit, list, delete
- Goals: create, update, list, delete, contribute funds
- Demo seed: populate a fresh account with six months of representative data

Every mutation is scoped to the current JWT identity, so one user cannot edit another user's finance records through an object ID.

## Authentication

The API uses JWT access tokens. The frontend stores the access token in local storage for this portfolio MVP and sends it with `Authorization: Bearer <token>` for protected requests.

For a higher-security production finance product, the next authentication step would be short-lived access tokens plus rotating refresh tokens stored in secure HTTP-only cookies.

## Database strategy

`DATABASE_URL` controls persistence. Local development defaults to SQLite. Production deployments can supply a PostgreSQL connection string with no domain-model changes.

## Frontend product structure

The client exposes four primary product areas:

1. **Overview** — key metrics, six-month cash-flow visualization, category spending, budget health, goals, and insights.
2. **Transactions** — create/edit/delete, notes, search, category filter, and income/expense filter.
3. **Budgets** — category guardrails with live spent/remaining calculations, edit/delete actions, and over-budget states.
4. **Goals** — goal CRUD, direct contributions, aggregate progress, and completion states.

The interface intentionally uses native React/TypeScript and CSS instead of a component or chart framework so the interaction and visualization logic remains visible in the portfolio code.

## UI system

Ledgerly uses a dark fintech visual system:

- Background: `#090D0B`
- Surface: `#111A15`
- Elevated surface: `#16221B`
- Brand green: `#22C55E`
- Positive: `#4ADE80`
- Warning: `#F59E0B`
- Danger: `#EF4444`
- Primary text: `#F4F7F5`
- Secondary text: `#94A39A`

The dashboard adapts from a sticky desktop sidebar to compact horizontal navigation, then single-column content on smaller screens.
