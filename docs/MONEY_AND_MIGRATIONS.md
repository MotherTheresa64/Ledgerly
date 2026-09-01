# Money semantics and schema migrations

## Why Ledgerly does not use Float for money

Binary floating point cannot represent many decimal currency values exactly. Ledgerly therefore treats decimal cents as a domain invariant rather than a display-formatting concern.

Authoritative money fields use:

- PostgreSQL / SQLite SQLAlchemy type: `NUMERIC(14,2)`
- Python: `Decimal`
- cent quantum: `Decimal("0.01")`
- rounding: `ROUND_HALF_UP`
- maximum absolute value: `999,999,999.99`

The fixed-precision fields are:

- `financial_account.opening_balance`
- `transaction.amount`
- `budget.limit`
- `goal.target`
- `goal.saved`

`server/app/money.py` owns parsing, rounding, summation, percentage, and API serialization helpers. User-supplied money is not converted through Python `float` before validation/calculation. JSON numbers are produced only at the HTTP boundary for browser compatibility.

## Accepted input

Normal decimal literals such as these are accepted and rounded deliberately to cents:

```text
0.01
10.10
1.005   -> 1.01
-25.50
999999999.99
```

Ledgerly rejects:

- NaN
- positive/negative infinity
- scientific notation such as `1e5`
- values outside the supported range
- zero where the operation requires a positive/non-zero amount

The UI normally lets a user enter a positive amount and choose Income or Expense; signed storage is an internal/domain representation.

## Account sign semantics

### Asset-oriented accounts

Checking, savings, cash, investment, and other accounts use the signed opening/current balance directly.

### Liability accounts

Credit and loan accounts represent debt as a negative internal balance.

If a user creates a credit account with `$500` owed:

```text
UI opening debt:        500.00
stored opening balance: -500.00
```

A `$100` card expense stores `-100.00` and produces `-600.00` debt. A `$200` transfer/payment into the card stores `+200.00` on the card side and produces `-400.00` debt.

This allows account balances to contribute directly to net worth:

```text
assets + signed liabilities = net worth
```

## Transfer invariants

A transfer creates exactly two entries under one `transfer_group`:

```text
source account      -amount
recipient account   +amount
```

Both entries are added and flushed in one SQLAlchemy transaction. On any database failure the session rolls back. A transfer:

- does not count as income;
- does not count as expense;
- does not change aggregate net worth;
- cannot be edited one side at a time;
- is deleted as a pair;
- prevents hard deletion of a participating account so historical pairing is preserved.

## Budget/category semantics

Budget matching normalizes category whitespace and compares categories case-insensitively. For example, `Groceries`, `groceries`, and `  GROCERIES ` resolve to the same budget matching key.

Budget spending includes only current-calendar-month expense transactions. Income and transfers are excluded.

## Goal semantics

Savings goal progress is informational unless the user separately records a real account transfer. Goal contributions do not silently claim that money moved in a bank account.

Overfunding is valid. Ledgerly preserves the full saved amount and reports:

- `percentComplete` (may be above 100)
- `isOverfunded`
- `overfundedBy`
- `amountRemaining` (floored at zero)

The visual progress bar may clamp at 100% while the underlying financial value remains unchanged.

## Migration authority

Ledgerly previously used `db.create_all()` and startup `ALTER TABLE` compatibility helpers. Those are no longer the schema authority.

The repository now uses Flask-Migrate/Alembic under `server/migrations/`.

Local migration:

```bash
cd server
flask --app run.py db upgrade
```

Render runs the same command as an API pre-deploy command before Gunicorn starts.

## First durable migration

Revision `20260901_01` is adaptive because some existing Ledgerly databases may have been modified by older startup schema helpers while a fresh database has no tables.

The revision can:

- create the current schema on a fresh database;
- add missing Firebase identity columns used by the current model;
- add account/transaction/goal fields introduced before durable migrations;
- backfill missing transaction types from the historical transaction sign;
- convert Float money columns to `NUMERIC(14,2)` without intentionally dropping financial rows;
- preserve existing IDs/data;
- add expected indexes;
- convert existing **positive** credit/loan opening balances to negative liability balances under the new documented convention.

## Production migration procedure

For the first production deployment containing revision `20260901_01`:

1. Take a PostgreSQL backup/snapshot.
2. Confirm the current deployment is healthy.
3. Deploy the new API build.
4. Let Render run `flask --app run.py db upgrade` before startup.
5. Confirm `/api/health` reports `money: decimal`.
6. Smoke-test a known account with simple hand arithmetic.
7. Create `0.01`, `10.10`, transfer, budget, goal, and import test records in a disposable account.
8. Verify credit/loan opening balances display as normal positive debt input but contribute negatively to net worth.
9. Confirm no old process is still running startup schema mutation code.

Do not reset/drop the production database to perform this migration.

## Downgrade note

The migration's technical downgrade relaxes fixed-precision money columns back to Float while preserving rows. It intentionally does **not** reverse liability signs because doing so after post-migration activity could silently change the economic meaning of account history.

A production rollback should therefore restore the pre-migration database snapshot if exact old semantics are required.

## Regression coverage

Backend tests cover:

- repeated `0.01` additions
- half-cent rounding
- `10.10`
- maximum/out-of-range values
- NaN/infinity/scientific notation rejection
- liability/net-worth behavior
- paired transfers and rollback
- budget category normalization
- goal overfunding
- decimal import fingerprints
- migration of a simulated legacy Float SQLite schema
- creation of a fresh schema through Alembic
