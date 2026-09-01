# Ledgerly architecture

## System overview

Ledgerly is a full-stack monorepo with four clear responsibility boundaries:

```text
React / TypeScript SPA
        │
        ├── Firebase Web Authentication
        │
        └── HTTPS JSON + Firebase ID token
                    │
                    ▼
              Flask API
        ┌───────────┼────────────┐
        │           │            │
 Firebase Admin   finance      validation /
 verification     services      calculations
        │           │            │
        └───────────┴─────┬──────┘
                          ▼
                    PostgreSQL
```

- `client/` owns presentation, interaction state, Firebase browser auth, CSV parsing/export, and typed HTTP calls.
- Firebase owns credentials, email verification, password reset/change, and recent-login reauthentication.
- `server/` owns authorization, finance-domain validation/calculation, persistence, destructive operations, and export.
- PostgreSQL is the production source of truth for financial records; SQLite is supported for local development/tests.

## Backend modules

- `app/firebase_auth.py` — Firebase Admin initialization, token verification/revocation, verified-email enforcement, UID mapping, legacy-user linking, backend Firebase deletion.
- `app/money.py` — fixed-precision money parsing/rounding/summation/serialization.
- `app/models.py` — SQLAlchemy finance models using `NUMERIC(14,2)` for authoritative money.
- `app/routes.py` — authenticated account, dashboard, transaction, transfer, import/export, budget, goal, demo, and destructive-data endpoints.
- `app/config.py` — database/environment configuration.
- `migrations/` — durable Alembic schema history.
- `tests/` — auth/ownership/domain/migration/regression tests.

## Frontend modules

`App.tsx` remains the primary product surface. Focused modules isolate cross-cutting behavior instead of making that component larger:

- `api.ts` — authenticated API client, timeouts, malformed-response handling, mutation guardrails.
- `mobileNavigation.ts` — accessible phone navigation state.
- `transactionPagination.ts` — desktop numbered pagination and compact phone pagination.
- `inputGuardrails.ts` — transaction text limits/counters.
- `financialSemantics.ts` — compatibility label updates while the backend contract evolves from “balance” to net-worth/liquidity terminology.
- `readiness.css` — final responsive, touch-target, overflow, focus, and reduced-motion hardening.
- `ThemeSwitcher.tsx` / theme CSS — appearance without changing finance semantics.

## Identity boundary

Firebase is the credential authority; Ledgerly is the finance-data authority.

On a protected request:

1. the browser gets the current Firebase ID token;
2. the Flask API verifies signature, expiry, project, and revocation state with Firebase Admin;
3. production normally requires `email_verified=true`;
4. the verified UID maps to one internal Ledgerly `User` row;
5. routes derive the internal `user_id` from that authenticated mapping;
6. finance queries include that internal user id server-side.

No request payload may override the authenticated internal user id.

## Legacy Firebase migration

A pre-Firebase Ledgerly account may be linked to a Firebase identity only when:

- Firebase has verified the bearer token;
- the token contains a verified email;
- an existing Ledgerly row has the same normalized email;
- that row is not already linked to a different Firebase UID.

A Firebase UID whose email changes is updated only if the destination email is not already owned by another Ledgerly row. Database uniqueness failures are rolled back safely.

The historical non-null `password_hash` column remains for compatibility with existing databases. New Firebase users receive an unusable random placeholder; Ledgerly never authenticates against it.

## Domain model

### User

Owns all financial objects and stores the Firebase UID mapping.

### FinancialAccount

Represents checking, savings, cash, credit, loan, investment, or other accounts. It stores an opening balance, archive state, include-in-totals choice, institution, and description.

Credit/loan balances are liabilities and are negative internally. The API exposes a positive-form opening debt value for normal user input while returning signed current/net-worth contribution values.

### Transaction

Stores one signed cash-flow entry with optional account, subcategory, tags, notes, transfer group, and date.

- income = positive
- expense = negative
- transfer = paired negative/positive entries

### Budget

Stores a monthly category limit. Spending is derived from current-month expense transactions with case/whitespace-normalized category matching.

### Goal

Stores target, saved amount, optional target date, and notes. Contributions update tracking progress only; they do not imply an account transfer.

## Money boundary

All authoritative monetary values use SQL `NUMERIC(14,2)` and Python `Decimal`. `server/app/money.py` performs cent quantization with `ROUND_HALF_UP`, finite/range validation, and Decimal summation.

The JSON contract still uses JavaScript-friendly numbers, but conversion happens only after authoritative calculations are complete.

## Dashboard read model

`GET /api/dashboard` returns one user-scoped read model with:

- net worth (`totalBalance` remains a compatibility alias)
- liquid balance context
- asset and liability totals
- current-month income/expenses/net cash flow/savings rate
- category spending
- budgets and unbudgeted spending
- account balances
- transaction history
- goal progress
- six-month trend
- monthly plan summary
- derived insights

Transfers are excluded from income/expense calculations. Archived/excluded accounts are handled separately from active included totals.

## Transfer integrity

A transfer request requires two distinct active accounts owned by the caller. The API creates both entries under one UUID transfer group and performs an explicit flush + commit inside one SQLAlchemy transaction.

If either insert/flush/commit fails, the session rolls back and the API reports that no transfer was saved.

Individual transfer entries cannot be edited. Deleting either side deletes all entries in its user-scoped transfer group. Accounts with historical transfers cannot be hard-deleted; they can be archived so the transfer ledger remains intelligible.

## Import model

The browser parses CSV into typed transaction JSON. The server remains authoritative for validation.

The API supports:

- max 1,000 rows/request
- an optional active default account
- decimal parsing and cent rounding
- normal transaction/account validation
- normalized duplicate fingerprints
- duplicate detection both against the database and earlier rows in the same request
- **atomic mode** (default)
- **partial mode** (explicit opt-in)

Settings deliberately opts into partial mode and communicates skipped invalid/duplicate rows. Other callers that omit `allowPartial` get atomic behavior.

## Export model

- browser CSV export covers transactions for convenient portability;
- `GET /api/export` returns accounts, transactions, budgets, goals, export timestamp, schema version, and money-semantics metadata;
- credentials, Firebase tokens, service-account material, and password placeholders are never exported.

The JSON backup is currently an export/inspection artifact, not an automatic restore endpoint.

## Destructive operations

### Clear finance data

`DELETE /api/data` requires explicit `CLEAR` confirmation and removes only the authenticated user's finance objects, not their identity.

### Demo reset

`POST /api/demo/reset` requires explicit `RESET` confirmation because it replaces current finance data with fictional sample records.

### Account deletion

The client requires Firebase recent-login reauthentication. The API additionally requires `DELETE` confirmation and then:

1. deletes finance records;
2. deletes the server-bound Firebase UID;
3. deletes Ledgerly account metadata.

External partial failures are returned explicitly so the UI/support path can distinguish `dataDeleted`, `firebaseDeleted`, and `metadataDeleted` state.

## Error behavior

The client:

- refreshes the Firebase token through the SDK;
- times requests out rather than hanging indefinitely;
- distinguishes network/timeout/malformed API responses;
- clears the UI session gate on `401`;
- waits for successful API commits before displaying success.

The API:

- uses bounded request bodies;
- validates JSON money/text input before route mutation;
- rolls back database state on handled transaction failures and generic server errors;
- avoids leaking Firebase credential/token details in errors/logs;
- returns no-store financial JSON.

## Schema evolution

Alembic/Flask-Migrate is now the schema authority. The app no longer calls `db.create_all()` or executes ad-hoc `ALTER TABLE` statements during production startup.

Revision `20260901_01` is adaptive so it can establish a fresh database or bring the previously startup-mutated Ledgerly schema under durable migration control. Render runs migrations before API startup.

See [`MONEY_AND_MIGRATIONS.md`](MONEY_AND_MIGRATIONS.md).

## Responsive/accessibility architecture

Desktop keeps the sticky sidebar and data-rich layouts. As width decreases:

- metrics and multi-column cards collapse progressively;
- phone navigation becomes a controlled menu with `aria-expanded`, Escape support, and outside-click close;
- form rows and filters become single-column;
- transaction rows stack instead of creating horizontal tables;
- phone pagination renders previous/current/next rather than every page button;
- controls maintain touch-friendly heights;
- long finance labels may wrap instead of forcing overflow;
- visible focus remains available;
- reduced-motion preference disables decorative transition/scroll animation.

Financial status is also communicated in text (transaction type, budget status, labels), not solely by theme accent color.

## Deployment

Render hosts PostgreSQL, the Flask/Gunicorn API, and the Vite static frontend. Firebase remains the external identity provider.

API deploy order:

```text
install dependencies
      ↓
flask --app run.py db upgrade
      ↓
gunicorn run:app
      ↓
/api/health
```

Production still requires correct Firebase Admin credentials, client Firebase Web config, `CLIENT_ORIGIN`, `VITE_API_URL`, and Firebase authorized domains.
