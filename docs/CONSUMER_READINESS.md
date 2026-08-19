# Ledgerly consumer readiness

Ledgerly v1.0 is designed as a deployable personal-finance application rather than a demo-only CRUD project.

## Account security

- Firebase Authentication is the identity provider for registration, login, verification, password recovery, and password changes.
- New accounts must verify their Firebase email before financial data can be accessed when `FIREBASE_REQUIRE_VERIFIED_EMAIL=true`.
- The browser sends Firebase ID tokens to the Flask API over HTTPS.
- Flask verifies token authenticity, expiry, revocation state, project ownership, and verified-email status with the Firebase Admin SDK.
- The Firebase UID is mapped to exactly one internal Ledgerly user record used for finance ownership.
- Existing pre-Firebase Ledgerly accounts can be linked by the same verified email, preserving existing finance history.
- Password changes and account deletion use Firebase reauthentication so sensitive actions require a recent login.
- Password reset email is sent by Firebase and does not require Ledgerly to operate its own SMTP or transactional-email service.
- API responses use restrictive security headers and financial JSON responses are not cached.

## Identity infrastructure

Production requires one Firebase project with:

- a registered Firebase Web app
- Email/Password Authentication enabled
- the Ledgerly frontend host listed in Authorized domains
- a Firebase Admin service account available only to the Flask backend

Frontend environment values:

```text
VITE_FIREBASE_API_KEY
VITE_FIREBASE_AUTH_DOMAIN
VITE_FIREBASE_PROJECT_ID
VITE_FIREBASE_APP_ID
```

Backend environment values:

```text
FIREBASE_PROJECT_ID
FIREBASE_SERVICE_ACCOUNT_JSON
FIREBASE_REQUIRE_VERIFIED_EMAIL=true
```

The Firebase Web configuration is browser configuration, not a private server credential. `FIREBASE_SERVICE_ACCOUNT_JSON` is privileged and must remain backend-only.

See [`FIREBASE_SETUP.md`](FIREBASE_SETUP.md) for the exact deployment process.

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

1. Register with a real inbox through Firebase Authentication.
2. Confirm the account cannot access Ledgerly finance data until the email is verified.
3. Verify the email and confirm the Ledgerly dashboard loads.
4. Request a password reset and confirm Firebase's reset email arrives.
5. Change the password from Ledgerly Settings and confirm the old password no longer authenticates.
6. Sign out, refresh, and confirm protected finance data remains inaccessible.
7. Sign in again and confirm finance history persists.
8. Seed demo data, create/edit/delete a transaction, and refresh to confirm PostgreSQL persistence.
9. Exercise budgets, goals, CSV import/export, clear-data, and account deletion.
10. Verify Midnight, Emerald, Violet, Amber, and Light themes persist across refreshes.
11. Verify layout at 320px, 360px, 390px, 430px, tablet, and desktop widths.
12. Verify production CORS only allows the intended Ledgerly frontend origin.
13. Verify a second Firebase account cannot access the first user's transactions, budgets, or goals.
14. Delete a disposable account and confirm the Ledgerly data and Firebase user are both removed.
15. Rotate any database or Firebase service-account credential accidentally exposed during deployment setup.
