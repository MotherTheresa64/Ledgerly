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
- Authentication endpoints are rate limited by client IP.
- API responses use restrictive security headers and financial JSON responses are not cached.

## Transactional email

Ledgerly supports two delivery paths:

1. **Resend HTTPS API** — preferred when a verified sending domain is available.
2. **Authenticated SMTP fallback** — useful for a dedicated Gmail or other SMTP mailbox while a custom domain is not yet available.

Core environment variables:

- `EMAIL_FROM`
- `PUBLIC_APP_URL`
- `EMAIL_VERIFICATION_REQUIRED=true`

Resend:

- `RESEND_API_KEY`

SMTP fallback:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_USE_SSL`

If both are configured, Ledgerly tries Resend first and falls back to SMTP when Resend cannot deliver. Production must have at least one delivery method capable of reaching arbitrary customer inboxes before email verification is enforced publicly.

For Gmail SMTP, use a dedicated mailbox, 2-Step Verification, and an app password rather than the normal Google-account password. Do not reuse a personal primary mailbox for a long-term public product.

## Appearance

- The default visual theme is Midnight, a neutral blue/navy palette.
- Users can switch between Midnight, Emerald, Violet, Amber, and Light.
- Theme choice persists in the browser.
- Income, expense, warning, and destructive-action colors retain their semantic meaning regardless of accent theme.

## Mobile behavior

- The app renders at native mobile browser zoom using the standard viewport meta tag.
- At phone widths, navigation becomes a bounded layout rather than an overflowing rail.
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
8. Verify Midnight, Emerald, Violet, Amber, and Light themes persist across refreshes.
9. Verify layout at 320px, 360px, 390px, 430px, tablet, and desktop widths.
10. Verify production CORS only allows the intended Ledgerly frontend origin.
11. Rotate any database or email credentials exposed during deployment setup.
