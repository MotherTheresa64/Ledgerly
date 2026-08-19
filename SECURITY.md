# Security policy

Ledgerly is designed as a publicly deployable personal-finance application. Security-sensitive changes should preserve the controls documented here and remain covered by automated tests.

## Supported version

The `main` branch is the supported release line.

## Reporting a vulnerability

Please report security issues privately to the repository owner rather than opening a public issue. Include reproduction steps, affected endpoint/component, and potential impact. Do not include real financial data, passwords, access tokens, database URLs, or email-provider credentials in a public issue.

## Security characteristics

- Passwords are hashed with Werkzeug password hashing helpers and are never stored in plaintext.
- Production registration requires verification of the submitted email address before protected finance data can be accessed.
- Email-verification links are cryptographically signed, expire after 24 hours by default, and become unusable after successful verification or replacement.
- Password-reset links are cryptographically signed, expire after one hour by default, and are single-use.
- Forgot-password and resend-verification responses are deliberately generic so callers cannot reliably enumerate registered accounts.
- Public authentication endpoints are protected by durable per-IP rate limits backed by the application database.
- Passwords must be 10–128 characters and contain at least one letter and one number.
- Protected API routes require signed JWT access tokens with a finite lifetime (`JWT_ACCESS_TOKEN_HOURS`, 12 hours by default).
- JWTs carry an account authentication version. Password changes and password resets increment that version, invalidating tokens issued to other sessions.
- Every transaction, budget, goal, and account mutation is scoped to the authenticated user.
- Password changes require the current password. Account deletion requires password confirmation and removes associated finance data.
- Server-side validation is applied before transaction imports and mutations are committed.
- Request bodies are capped to prevent oversized API payloads.
- API responses set defensive content/frame/referrer/permissions headers and JSON responses are marked `no-store`.
- CORS is restricted to the configured `CLIENT_ORIGIN`.
- Production secrets are supplied through environment variables and must not be committed.
- CI runs backend tests on Python 3.12 and 3.14, frontend type checking, a production build, and an npm high-severity audit.

## Deployment requirements

Public production deployments must use HTTPS and PostgreSQL, strong distinct values for `SECRET_KEY` and `JWT_SECRET_KEY`, a restricted `CLIENT_ORIGIN`, the correct `PUBLIC_APP_URL`, and `EMAIL_VERIFICATION_REQUIRED=true`.

Transactional email requires a protected `RESEND_API_KEY` and an `EMAIL_FROM` address using a sender/domain authorized by the email provider. Rotate any database, JWT, application, or email-provider credential that is accidentally disclosed.

## Authentication storage note

The current React SPA and API are deployed on separate Render services. The SPA stores its short-lived bearer access token in browser local storage so it can call the stateless cross-origin API. Invalid, expired, or server-revoked tokens are removed automatically, and Ledgerly never stores passwords or financial credentials in browser storage.

This architecture makes client-side XSS prevention important. The UI relies on React escaping and does not inject user-provided HTML. A future same-origin/BFF deployment can move the bearer token into a Secure, HttpOnly cookie for additional browser-level isolation without changing the finance domain model.
