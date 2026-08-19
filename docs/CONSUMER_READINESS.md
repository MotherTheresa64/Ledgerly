# Ledgerly consumer readiness

Ledgerly v1.0 is designed as a deployable personal-finance application rather than a demo-only CRUD project.

## Account security

- New production accounts require email verification before financial data can be accessed.
- Verification links are signed, time-limited, and one-time-use.
- Verification can be resent without revealing account state through the public response.
- Password reset requests do not reveal whether an email address is registered.
- Password reset links are signed, time-limited, and one-time-use.
- Password changes and resets increment an account auth version, revoking previously issued access tokens.
- Existing accounts created before email verification shipped are grandfathered as verified during the schema upgrade.
- Passwords must be 10–128 characters and contain at least one letter and one number.

## Email delivery

Production transactional email uses Resend through the HTTPS API. The backend requires these environment variables for delivery:

- `RESEND_API_KEY`
- `EMAIL_FROM` (for example `Ledgerly <hello@ledgerly.example>`)
- `PUBLIC_APP_URL`
- `EMAIL_VERIFICATION_REQUIRED=true`

The application remains testable without an email provider by disabling verification only in test configuration. Production should keep verification enabled.

## Mobile behavior

- The app renders at native mobile browser zoom using the standard viewport meta tag.
- At phone widths, navigation becomes a bounded two-row grid instead of an overflowing horizontal rail.
- Dashboard cards, forms, filters, transaction rows, charts, account controls, and authentication forms are constrained to the viewport.
- Form fields use mobile-safe sizing to avoid focus zoom and touch targets maintain usable height.

## Production QA checklist

1. Register with a real inbox and verify the email.
2. Confirm unverified login is blocked.
3. Resend verification and confirm the newest link works.
4. Request a password reset, use it once, and confirm reuse fails.
5. Confirm an already-issued session is rejected after password reset/change.
6. Seed demo data, create/edit/delete a transaction, and refresh to confirm PostgreSQL persistence.
7. Exercise budgets, goals, CSV import/export, clear-data, and account deletion.
8. Verify layout at 320px, 360px, 390px, 430px, tablet, and desktop widths.
9. Verify production CORS only allows the intended Ledgerly frontend origin.
10. Rotate any database or email credentials exposed during deployment setup.
