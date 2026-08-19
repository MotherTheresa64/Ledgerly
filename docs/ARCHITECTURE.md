# Ledgerly architecture

## Overview

Ledgerly uses a small monorepo structure:

- `client/` — React + TypeScript SPA
- `server/` — Flask REST API
- `server/app/models.py` — relational finance domain models
- `server/app/routes.py` — authenticated API endpoints
- `.github/workflows/ci.yml` — frontend build + backend test pipeline

## Domain model

A `User` owns `Transaction`, `Budget`, and `Goal` records. Transactions are signed values: income is positive and expenses are negative. Budget progress is computed from expense transactions in the current calendar month for the matching category. Savings goals store a target amount and current saved amount.

## Authentication

The API uses JWT access tokens. The frontend stores the access token in local storage for this portfolio MVP and sends it with `Authorization: Bearer <token>` for protected requests.

## Database strategy

`DATABASE_URL` controls persistence. Local development defaults to SQLite. Production deployments can supply a PostgreSQL connection string with no model changes.

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

The dashboard is responsive and collapses the desktop sidebar into a top navigation bar on smaller screens.
