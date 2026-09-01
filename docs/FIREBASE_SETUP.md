# Firebase Authentication setup

Ledgerly uses Firebase Authentication for identity and keeps authoritative finance data in PostgreSQL.

## 1. Create/register a Firebase Web app

In Firebase Console:

1. Create or select the Ledgerly Firebase project.
2. Register a Web app.
3. Copy the browser configuration values.

Ledgerly's Vite frontend expects:

```text
VITE_FIREBASE_API_KEY
VITE_FIREBASE_AUTH_DOMAIN
VITE_FIREBASE_PROJECT_ID
VITE_FIREBASE_APP_ID
```

These Web SDK values are intentionally browser-visible configuration. They are not Firebase Admin private credentials.

## 2. Enable Email/Password Authentication

Under **Authentication → Sign-in method**, enable **Email/Password**.

Firebase owns:

- registration
- sign-in
- email verification
- password reset
- password changes
- recent-login reauthentication

Ledgerly's backend does not run its own password login endpoint.

## 3. Configure authentication policy

Recommended production settings:

- keep `FIREBASE_REQUIRE_VERIFIED_EMAIL=true` on the API;
- configure a strong Firebase password policy appropriate for the deployment;
- enable email-enumeration protection if available/appropriate;
- review Firebase abuse/quota protections;
- customize verification/reset emails if presenting Ledgerly publicly.

The backend verifies Firebase ID tokens with revocation checking. A valid but unverified email cannot enter the finance API while verified-email enforcement is enabled.

## 4. Add authorized domains

Under **Authentication → Settings → Authorized domains**, authorize:

```text
localhost
<your Ledgerly frontend Render/custom domain>
```

Do not assume a prior Render hostname is still correct; use the exact deployed frontend host.

## 5. Configure Firebase Admin on the API

The Flask API needs a trusted Admin credential to verify tokens and delete a Firebase user during permanent Ledgerly account deletion.

Supported configuration paths:

### Render environment JSON

```text
FIREBASE_PROJECT_ID=<project id>
FIREBASE_SERVICE_ACCOUNT_JSON=<single-line service-account JSON>
FIREBASE_REQUIRE_VERIFIED_EMAIL=true
```

### Protected secret file / Application Default Credentials

```text
GOOGLE_APPLICATION_CREDENTIALS=<path to protected service-account file>
FIREBASE_PROJECT_ID=<project id>
FIREBASE_REQUIRE_VERIFIED_EMAIL=true
```

Never place a service-account private key in the frontend, Git repository, screenshots, logs, or public issue text.

## 6. Configure the Render frontend

Set on the static frontend service:

```text
VITE_API_URL=https://<ledgerly-api-host>/api
VITE_FIREBASE_API_KEY=<Firebase Web apiKey>
VITE_FIREBASE_AUTH_DOMAIN=<Firebase authDomain>
VITE_FIREBASE_PROJECT_ID=<Firebase project id>
VITE_FIREBASE_APP_ID=<Firebase Web app id>
```

Vite consumes these at build time, so changing them requires a rebuild/redeploy.

## 7. Configure the Render API

Set/verify:

```text
CLIENT_ORIGIN=https://<exact-ledgerly-frontend-host>
FIREBASE_PROJECT_ID=<project id>
FIREBASE_SERVICE_ACCOUNT_JSON=<protected Admin JSON>
FIREBASE_REQUIRE_VERIFIED_EMAIL=true
```

`DATABASE_URL` is supplied by the Render PostgreSQL binding in `render.yaml`.

The API deployment runs:

```text
flask --app run.py db upgrade
```

before Gunicorn starts. Take a PostgreSQL backup before the first deployment containing the fixed-precision migration; see [`MONEY_AND_MIGRATIONS.md`](MONEY_AND_MIGRATIONS.md).

## 8. Firebase UID → Ledgerly user mapping

On each protected request:

1. browser sends the current Firebase ID token;
2. Firebase Admin verifies it (including revocation state);
3. Ledgerly reads the verified `uid`, `email`, and `email_verified` claims;
4. existing `firebase_uid` mapping is used when present;
5. otherwise, a pre-Firebase Ledgerly row can be linked by the same **verified** email if it is not already linked to another UID;
6. otherwise a new Ledgerly user is created.

If a mapped Firebase user's email changes, Ledgerly updates the local email only when it does not collide with another Ledgerly account.

The historical non-null `password_hash` column may remain in an upgraded database. New Firebase users receive a random unusable placeholder because Firebase, not Ledgerly, is the password authority.

## 9. Permanent account deletion

The browser first reauthenticates the user with Firebase to satisfy recent-login requirements.

The API then receives an authenticated account-deletion request with explicit `DELETE` confirmation and uses the Firebase UID already mapped to that Ledgerly user. The client cannot select a different UID to delete.

Deletion stages:

1. Ledgerly finance data;
2. Firebase user via Admin SDK;
3. Ledgerly user metadata.

If Firebase deletion fails after financial records were removed, the endpoint returns explicit partial-state information and keeps the Ledgerly identity row available for a retry/support path. This is safer than silently reporting success across two independent services.

## 10. Production smoke test

Use disposable test accounts/data:

1. Register a new Firebase Email/Password account.
2. Confirm finance access is denied before verification.
3. Verify the email and open Ledgerly.
4. Add accounts, including a credit/loan account, and verify liability/net-worth behavior.
5. Add income and expense transactions.
6. Transfer between two accounts and confirm income/expenses do not change.
7. Refresh and confirm PostgreSQL persistence.
8. Sign out and verify protected data is not accessible.
9. Sign in again.
10. Test Forgot Password and password change.
11. Test CSV import/export and JSON backup export.
12. Test budgets/goals, including an overfunded goal.
13. Test the live layout at phone/tablet/desktop widths.
14. Delete a disposable account and verify the Firebase user can no longer sign in and Ledgerly finance data is gone.
15. Inspect API logs to ensure tokens/service-account material are not logged.

## Troubleshooting

### `firebase_not_configured` / HTTP 503

The API cannot initialize Firebase Admin. Verify project id and Admin credentials are present in the API environment.

### HTTP 401 for a valid login

Check:

- email verification status;
- Firebase project mismatch between client and API;
- token revocation/expiration;
- authorized frontend domain;
- whether the local email is already bound to a different Firebase UID.

### CORS failure

Set `CLIENT_ORIGIN` to the exact frontend origin, including scheme and without an unrelated path.

### Account deletion fails after finance data removal

Read the endpoint's partial-state fields. If `dataDeleted=true` and `firebaseDeleted=false`, the authenticated identity still exists and the deletion can be retried after Firebase/Admin configuration is repaired.
