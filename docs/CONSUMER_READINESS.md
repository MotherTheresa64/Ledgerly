# Ledgerly production readiness

Ledgerly is designed as a deployable personal-finance application rather than a demo-only CRUD project. The repository's automated gates cover the core invariants, while the checklist below captures deployment and hands-on verification that depends on real Firebase/Render infrastructure.

## Account security

- Firebase Authentication is the identity provider for registration, login, verification, password recovery, password changes, and reauthentication.
- New accounts must verify their Firebase email before financial data can be accessed when `FIREBASE_REQUIRE_VERIFIED_EMAIL=true`.
- The browser retrieves the active Firebase user's ID token when an API request is made; Ledgerly does not persist that bearer token in its own local storage.
- Flask verifies token authenticity, expiry, revocation state, project ownership, and verified-email status with the Firebase Admin SDK.
- The Firebase UID maps to exactly one internal Ledgerly user used for finance ownership.
- Existing pre-Firebase Ledgerly accounts can be linked by the same verified email, preserving finance history.
- Password changes and account deletion use Firebase reauthentication so sensitive actions require a recent login.
- API responses use restrictive security headers, finance JSON is `no-store`, and errors do not expose stack traces.
- Protected resource lookups are scoped server-side; client-side filtering is never treated as authorization.

## Financial correctness

- Canonical balances, transactions, budgets, and goal values are stored as integer cents.
- API money parsing uses `Decimal` and rejects non-finite values, fractional cents, invalid zero/negative cases, and values beyond the supported maximum.
- Legacy float columns are compatibility mirrors only; an additive startup migration backfills cents for existing deployments.
- Transfers are paired and excluded from income/expense analytics.
- Budget percentages remain numerically correct above 100%.
- Current-period calculations accept the browser's local `asOf` date so month boundaries are not determined accidentally by the API host timezone.

## Identity infrastructure

Production requires one Firebase project with:

- a registered Firebase Web app
- Email/Password Authentication enabled
- the Ledgerly frontend host listed in Authorized domains
- Firebase Admin credentials available only to the Flask backend

Frontend environment values are documented in `client/.env.example`; backend values are documented in `server/.env.example`.

The Firebase Web configuration is browser configuration, not a private server credential. Firebase Admin credentials are privileged and must remain backend-only.

See [`FIREBASE_SETUP.md`](FIREBASE_SETUP.md) for deployment setup.

## Appearance and responsive behavior

- Theme choice persists in the browser.
- Income, expense, warning, and destructive-action colors retain their semantic meaning across themes.
- The app renders at native mobile browser zoom using the standard viewport meta tag.
- Phone navigation is touch-oriented rather than an overflowing desktop rail.
- Dashboard cards, forms, filters, transaction rows, charts, account controls, dialogs, and authentication forms are constrained to the viewport.
- Form fields use mobile-safe sizing and touch targets maintain usable dimensions.
- Visible focus states and semantic status/error messaging support keyboard and assistive-technology use.

## Automated repository gates

Every pull request runs:

- frontend dependency installation
- `npm audit --audit-level=high`
- strict TypeScript typechecking, including unused-local/parameter checks
- Vite production build
- Ruff backend linting
- pytest on Python 3.12
- pytest on Python 3.14

The backend suite includes authentication boundaries, user isolation, transaction/account/transfer flows, imports, budgets/goals, exact-cent arithmetic, month boundaries, over-budget behavior, safe API errors, and schema migration/backfill.

## Production smoke-test checklist

1. Register with a disposable real inbox through Firebase Authentication.
2. Confirm the account cannot access Ledgerly finance data until the email is verified.
3. Verify the email and confirm the dashboard loads.
4. Request a password reset and confirm Firebase's reset email arrives.
5. Change the password from Settings and confirm the old password no longer authenticates.
6. Sign out, refresh, and confirm protected finance data remains inaccessible.
7. Sign in again and confirm finance history persists.
8. Seed fictional demo data, create/edit/delete a transaction, and refresh to confirm PostgreSQL persistence.
9. Create accounts and a transfer; confirm total net worth does not change from the transfer alone.
10. Exercise budgets above and below 100%, goals, CSV import/export, clear-data, and demo reset.
11. Verify themes persist across refreshes and every semantic state remains readable.
12. Verify layout at 320px, 360px, 390px, 430px, tablet portrait/landscape, normal laptop, and wide desktop widths.
13. Verify 200% browser zoom remains usable without hiding critical controls.
14. Verify keyboard-only navigation through authentication, navigation, forms, destructive confirmations, and settings.
15. Verify production CORS only allows intended Ledgerly frontend origins.
16. Verify a second Firebase account cannot access the first user's accounts, transactions, budgets, goals, exports, or mutations.
17. Delete a disposable account and confirm Ledgerly finance/account data and the Firebase user are both removed.
18. Review Render logs for uncaught errors and confirm no finance payloads, credentials, or bearer tokens are logged.
19. Confirm `/api/health` responds successfully from the deployed API.
20. Rotate any database or Firebase Admin credential accidentally exposed during deployment setup.
