# Security policy

Ledgerly is a publicly deployable personal-finance application. Security-sensitive changes should preserve the controls below and remain covered by automated tests.

## Supported version

The `main` branch is the supported release line.

## Reporting a vulnerability

Report security issues privately to the repository owner rather than opening a public issue. Include reproduction steps, the affected endpoint/component, and potential impact. Never place real financial data, passwords, Firebase ID tokens, database URLs, or service-account credentials in a public report.

## Identity and authentication

- Firebase Authentication is the sole credential authority for Ledgerly users.
- The Flask finance API never receives or validates the user's Firebase password.
- The browser uses Firebase for registration, sign-in, email verification, password reset/change, and recent-login reauthentication.
- Protected API calls send a Firebase ID token in `Authorization: Bearer ...` over HTTPS.
- Firebase Admin verifies the token and requests revocation checking.
- Production defaults to requiring a verified Firebase email.
- The verified Firebase UID maps to one internal Ledgerly user id; request payloads cannot override that ownership identity.
- A pre-Firebase Ledgerly account may be linked by email only after Firebase proves the email is verified.
- An email already mapped to a different UID cannot be claimed.
- Firebase email changes are checked for Ledgerly uniqueness before the local mapping is updated.

## Finance-data authorization / IDOR resistance

Every financial object is resolved under the authenticated internal user id:

- financial accounts
- transactions
- transfer groups
- budgets
- goals
- dashboard calculations
- imports
- exports
- data clearing
- demo seed/reset
- account deletion

Individual resource mutations query by both resource id and authenticated `user_id`. Cross-user guessed IDs return not-found/deny behavior without returning the other user's object.

Client-side filtering is not an authorization control.

## Money and validation security

Authoritative money uses SQL `NUMERIC(14,2)` and Python `Decimal`, not binary Float.

The API rejects unsafe monetary input including:

- NaN
- infinity
- scientific notation
- values above the supported magnitude
- zero/negative values where the operation requires positive money

Transaction text/tag lengths, account metadata, dates, account ownership, archive state, budget/goal values, and import size are also bounded server-side. Browser validation is only an additional UX layer.

## Transfer integrity

Transfers require two distinct active accounts belonging to the current user. Both entries are inserted in one SQLAlchemy transaction under one random transfer-group ID. An insert/flush failure rolls the session back.

One side cannot be edited independently. Deleting one side deletes the user-scoped pair. Accounts participating in historical transfers cannot be hard-deleted because that would destroy ledger meaning; they should be archived instead.

## Firebase legacy migration threat model

The only supported pre-Firebase ownership migration is:

```text
verified Firebase token
       +
verified email claim
       +
matching existing Ledgerly email
       +
existing record not linked to a different UID
       ↓
link Firebase UID to existing Ledgerly user
```

An unverified email is never sufficient to claim legacy financial history.

## Destructive operations

Destructive endpoints require server-side confirmation values in addition to UI confirmation:

- clear finance data → `CLEAR`
- replace with demo data → `RESET`
- permanently delete account → `DELETE`

Permanent account deletion also requires the browser to satisfy Firebase recent-login reauthentication first.

The backend deletes the Firebase identity by the UID already bound to the authenticated Ledgerly user. It never trusts a client-supplied UID for deletion.

Because Firebase and PostgreSQL are separate systems, the account-deletion endpoint reports partial-state fields if an external failure occurs after one stage has completed. It does not claim all-or-nothing behavior across two independent services.

## API/deployment controls

- API request bodies are bounded.
- CORS is limited to configured `CLIENT_ORIGIN` and expected methods/headers.
- JSON responses are marked `Cache-Control: no-store`.
- Responses set content-type, frame, referrer, permissions, and cross-origin-resource protections.
- Generic internal errors do not return stack traces or database details.
- Firebase verification failures do not log bearer tokens or credential material.
- Production database access is through the server-side `DATABASE_URL`.
- Schema changes are executed by Alembic before application startup rather than ad-hoc runtime `ALTER TABLE` statements.

## Secrets

Privileged backend values include:

```text
DATABASE_URL
SECRET_KEY
FIREBASE_SERVICE_ACCOUNT_JSON
GOOGLE_APPLICATION_CREDENTIALS (when used)
```

`FIREBASE_SERVICE_ACCOUNT_JSON` or the service-account secret file must never be placed in frontend environment variables, Git commits, screenshots, logs, issues, or client bundles.

Firebase Web configuration (`VITE_FIREBASE_*`) is intentionally browser-visible and is not equivalent to an Admin service-account credential.

Rotate any privileged credential that is accidentally exposed.

## Browser security note

The SPA relies on Firebase browser persistence and keeps a Ledgerly UI marker in local storage. API authorization does **not** trust that marker; each protected request obtains the current Firebase user's ID token and the backend verifies it independently.

That makes XSS prevention important. Ledgerly uses React rendering/escaping and does not intentionally inject user-provided HTML. Financial data is not intentionally cached to localStorage.

## Dependency / CI controls

Pull requests run:

Frontend:

- `npm audit --audit-level=high`
- Vitest regression tests
- TypeScript checks
- production Vite build

Backend:

- `pip check`
- Python compile check
- pytest on Python 3.12 and 3.14
- migration regression tests against fresh and simulated legacy SQLite schemas

Dependabot remains enabled for dependency/update visibility.

## Production requirements

A live deployment must configure:

```text
CLIENT_ORIGIN=<exact Ledgerly frontend origin>
FIREBASE_PROJECT_ID=<Firebase project id>
FIREBASE_SERVICE_ACCOUNT_JSON=<protected service-account JSON>
FIREBASE_REQUIRE_VERIFIED_EMAIL=true
```

The frontend needs its Firebase Web configuration and API URL, and the deployed frontend host must be listed in Firebase Authentication's authorized domains.

Before the first fixed-precision schema migration, create a PostgreSQL backup/snapshot. See [`docs/MONEY_AND_MIGRATIONS.md`](docs/MONEY_AND_MIGRATIONS.md).
