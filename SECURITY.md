# Security policy

Ledgerly is designed as a publicly deployable personal-finance application. Security-sensitive changes should preserve the controls documented here and remain covered by automated tests.

## Supported version

The `main` branch is the supported release line.

## Reporting a vulnerability

Please report security issues privately to the repository owner rather than opening a public issue. Include reproduction steps, affected endpoint/component, and potential impact. Do not include real financial data, passwords, Firebase ID tokens, database URLs, or service-account credentials in a public issue.

## Identity and authentication

- Firebase Authentication is the sole credential authority for Ledgerly users.
- Ledgerly's Flask API never receives or validates a user's login password.
- Email/password registration, sign-in, email verification, password reset, and password changes are handled by Firebase.
- New accounts must have a verified Firebase email before protected finance data can be accessed when `FIREBASE_REQUIRE_VERIFIED_EMAIL=true`.
- The React client obtains the active Firebase user's current ID token only when making API requests and sends it as a bearer token over HTTPS.
- Ledgerly does **not** copy Firebase bearer tokens into its own `localStorage`; the UI stores only a non-sensitive session marker.
- The Flask API verifies Firebase ID tokens with the Firebase Admin SDK, including revocation checking.
- The verified Firebase UID is mapped to one internal Ledgerly user record and cannot be claimed by another UID.
- Existing pre-Firebase Ledgerly records can be linked by the same verified email so finance history can survive the authentication migration.
- Password changes and account deletion require Firebase reauthentication in the client, which enforces Firebase's recent-login requirement.
- Password policy, abuse protections, and email-action behavior should be configured in the Firebase Authentication console.

## Finance-data authorization

- Every transaction, budget, goal, and account operation is scoped to the internal Ledgerly user resolved from a verified Firebase identity.
- A caller cannot select or override the internal user id through request data.
- Ownership checks are applied on reads and mutations of individual finance resources.
- Account deletion removes the user's Ledgerly finance data; the client then deletes the reauthenticated Firebase user.
- Server-side validation is applied before transaction imports and mutations are committed.
- Monetary values are parsed with `Decimal` and stored/calculated in canonical integer-cent columns; malformed, non-finite, fractional-cent, and oversized values are rejected.

## API and deployment controls

- Request bodies are capped to prevent oversized API payloads.
- Database errors roll back the active SQLAlchemy transaction and return a generic user-safe response.
- Unexpected exceptions are logged server-side while the client receives a generic error rather than a stack trace.
- API responses include a request ID for correlation without logging finance payloads.
- API responses set defensive content/frame/referrer/permissions headers and JSON responses are marked `no-store`.
- CORS is restricted to the configured `CLIENT_ORIGIN` value; multiple explicit origins can be comma-separated when necessary.
- Production uses HTTPS and PostgreSQL on Render.
- The Firebase Admin service-account credential is backend-only and must never be placed in frontend environment variables, committed files, screenshots, or public logs.
- Firebase Web configuration is intentionally browser-visible and is not a service-account secret.
- CI runs backend tests on Python 3.12 and 3.14, frontend type checking, a production build, and an npm high-severity audit.

## Deployment requirements

A public deployment should provide:

```text
CLIENT_ORIGIN=<Ledgerly frontend origin>
FIREBASE_PROJECT_ID=<Firebase project id>
FIREBASE_REQUIRE_VERIFIED_EMAIL=true
```

Provide Firebase Admin credentials through one supported backend-only mechanism:

```text
FIREBASE_SERVICE_ACCOUNT_JSON=<protected service-account JSON>
```

or:

```text
GOOGLE_APPLICATION_CREDENTIALS=<path to protected service-account file>
```

The frontend requires its Firebase Web app configuration and the Ledgerly API URL. The Ledgerly frontend domain must also be included in Firebase Authentication's authorized domains.

Rotate any service-account, database, or other privileged credential that is accidentally disclosed.

## Browser storage note

Ledgerly uses Firebase's browser authentication persistence. Its own `ledgerly_token` key is deliberately only the literal non-sensitive UI marker `firebase-session`; it is not a Firebase ID token and is never accepted by the API as authentication. API requests retrieve the active Firebase user's current token from the Firebase SDK and the backend independently verifies it.

This architecture still makes client-side XSS prevention important. The UI relies on React escaping and does not inject user-provided HTML. A future same-origin/BFF deployment could exchange Firebase identity for Secure, HttpOnly server sessions without changing the finance domain model.
