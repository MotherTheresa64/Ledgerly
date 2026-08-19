# Security policy

Ledgerly is a portfolio application, but it is implemented with production-minded security controls.

## Supported version

The `main` branch is the supported release line.

## Reporting a vulnerability

Please report security issues privately to the repository owner rather than opening a public issue. Include reproduction steps, affected endpoint/component, and potential impact.

## Security characteristics

- Passwords are hashed with Werkzeug's password hashing helpers and are never stored in plaintext.
- Protected API routes require signed JWT access tokens.
- Access tokens have a finite lifetime configured by `JWT_ACCESS_TOKEN_HOURS` (12 hours by default).
- Every transaction, budget, goal, and account mutation is scoped to the authenticated user.
- Password changes require the current password.
- Account deletion requires password confirmation and removes all associated application data.
- Server-side validation is applied to transaction imports and mutations before database writes.
- CORS is restricted to the configured `CLIENT_ORIGIN`.
- Production secrets are supplied through environment variables and must not be committed.
- CI runs backend tests, frontend type checking, a production build, and an npm high-severity audit.

## Deployment requirements

Production deployments must use HTTPS, strong generated values for `SECRET_KEY` and `JWT_SECRET_KEY`, a restricted `CLIENT_ORIGIN`, and PostgreSQL rather than the local SQLite fallback.

## Authentication storage note

The current SPA stores its short-lived access token in browser local storage for a simple stateless API deployment. This is a deliberate architecture tradeoff for this portfolio release. The application aggressively clears invalid/expired tokens and never stores passwords or financial credentials in browser storage. A future same-origin/BFF deployment could move authentication to an HttpOnly cookie without changing the finance domain model.
