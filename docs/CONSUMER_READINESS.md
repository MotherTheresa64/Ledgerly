# Ledgerly consumer readiness

Ledgerly v1.3 is designed as a deployable personal-finance application and portfolio-quality full-stack engineering project. This document distinguishes repository readiness from external deployment configuration.

## Repository readiness

### Financial correctness

- Authoritative money uses `NUMERIC(14,2)` + Python `Decimal`.
- Monetary input is rounded explicitly to cents with `ROUND_HALF_UP`.
- NaN, infinity, scientific notation, zero where invalid, and out-of-range values are rejected server-side.
- Repeated-cent additions, half-cent rounding, transfers, budgets, goals, imports, and maximum values have regression coverage.
- Credit/loan balances have explicit liability semantics and contribute negatively to net worth.
- Transfers are paired, user-scoped, database-atomic, excluded from income/expense analytics, and deleted together.
- Accounts with historical transfers must be archived rather than hard-deleted.
- Category matching for budgets is case/whitespace normalized.
- Goal overfunding is preserved and reported instead of silently capped.

### Authentication / ownership

- Firebase is the sole credential authority.
- Firebase ID tokens are verified server-side with revocation checking.
- Verified email is required by production-default configuration.
- Verified Firebase UID maps to one internal Ledgerly user.
- Legacy account linking requires a verified email and rejects conflicting UID ownership.
- Every finance object/ID is scoped server-side to the authenticated user.
- Cross-user resource/transfer tests exercise guessed IDs.

### Destructive operations

- clear-data requires server-side `CLEAR` confirmation;
- demo replacement requires `RESET` confirmation;
- account deletion requires Firebase recent-login reauthentication plus server-side `DELETE` confirmation;
- backend Firebase deletion uses the server-bound UID;
- multi-system account-deletion partial failure is surfaced explicitly rather than hidden.

### Data portability

- transaction CSV export;
- validated CSV import up to 1,000 rows;
- atomic API import by default;
- explicit partial-import mode used by Settings and communicated to the user;
- duplicate detection within an import and against existing rows;
- full JSON export of accounts, transactions, budgets, goals, schema version, and money semantics;
- credentials/auth secrets are not exported.

The full JSON backup is not currently an automated restore format and should not be advertised as one.

### Responsive/accessibility behavior

- desktop/sidebar navigation;
- accessible phone menu with `aria-expanded`, Escape, outside-click close;
- dense layouts collapse at tablet/phone widths;
- transaction history uses stacked rows rather than a wide mobile table;
- desktop pagination uses numbered pages/ellipses;
- phone pagination uses compact previous/current/next controls;
- filters and form rows collapse to one column on phones;
- long labels/amount context can wrap without forcing horizontal overflow;
- 44px+ touch controls for primary interactive elements;
- visible focus indicators;
- reduced-motion behavior;
- textual transaction/budget/status context in addition to semantic color.

### API failure behavior

The client handles:

- expired/unauthorized Firebase sessions;
- network failure;
- request timeout;
- malformed/unexpected server response;
- API validation errors;
- destructive/import/delete failure.

Success UI is shown after the authoritative API operation succeeds, not simply after an optimistic client mutation.

### Schema/deployment

- Flask-Migrate/Alembic owns schema evolution;
- startup `db.create_all()` / ad-hoc production ALTER hacks are removed;
- first durable migration handles fresh and legacy schemas;
- Render runs migrations before API startup;
- migration tests cover fresh and simulated legacy SQLite databases;
- first fixed-precision production deployment requires a database backup/snapshot.

## External production configuration still required

A live public deployment still needs:

- Firebase project and Web app;
- Email/Password provider enabled;
- production password/abuse/email settings reviewed;
- deployed frontend listed in Firebase authorized domains;
- Firebase Admin credential available only to the API;
- exact `CLIENT_ORIGIN`;
- frontend `VITE_API_URL`;
- frontend Firebase Web configuration;
- Render PostgreSQL database and successful migration;
- final live smoke testing.

Repository code cannot prove those external values are configured until the deployment is exercised.

## Appearance

Ledgerly retains its existing theme system. Semantic financial state should remain consistent across themes:

- income / success
- expense / destructive
- warning / approaching budget
- over-budget / error
- normal accent/navigation state

Accent choice should not redefine the meaning of a finance status.

## Recruiter/evaluator demo path

A reviewer should be able to understand the product without entering personal financial data:

1. register/verify a disposable account;
2. load fictional demo data into an empty account;
3. inspect overview/account/budget/goal/report screens;
4. create/edit/delete an income or expense transaction;
5. transfer between checking/savings and confirm no income/expense inflation;
6. inspect CSV/JSON portability;
7. switch to a phone-sized viewport and use compact transaction pagination;
8. inspect README/architecture/security/migration docs and tests.

Demo data is explicitly fictional and normal demo seeding refuses a non-empty account.

## Production QA checklist

### Authentication

1. Register with a real inbox.
2. Confirm unverified account cannot enter finance data.
3. Verify email and open Ledgerly.
4. Sign out/refresh and confirm protected data is inaccessible.
5. Sign back in and confirm data persists.
6. Test password reset.
7. Test password change/recent-login behavior.
8. Test token revocation if administratively practical.

### Money/accounts

9. Create checking, savings, cash, credit, loan, investment, and other account types.
10. Verify `$0.01`, `$10.10`, repeated additions, and a rounded 3-decimal input.
11. Verify credit/loan opening debt displays understandably and net worth uses liability signs.
12. Toggle archive/include-in-totals and verify dashboard behavior.

### Transactions/transfers

13. Create income and expense entries.
14. Test account/category/subcategory/tags/date/notes.
15. Edit/delete/search/filter/sort/paginate.
16. Transfer between two accounts and hand-check both balances + unchanged aggregate net worth.
17. Delete one transfer side and verify both entries disappear.
18. Attempt a cross-user account/transaction/transfer ID.
19. Attempt a transaction into an archived account.
20. Attempt hard deletion of an account with transfer history and confirm archive guidance.

### Budgets/goals/dashboard

21. Create/update/delete budgets with category casing/whitespace variations.
22. Test healthy/approaching/over thresholds and month boundaries.
23. Confirm income/transfers do not count toward budget spending.
24. Create/edit/delete goals, contribute, and overfund a goal.
25. Verify the UI does not claim a tracking-only goal contribution physically moved bank money.
26. Hand-calculate dashboard income/expense/net cash flow/net worth against a small known dataset.
27. Test no-income, negative-cash-flow, no-account, archived/excluded-account, and year/month-transition states.

### Import/export

28. Import quoted/comma-containing CSV.
29. Test decimal precision, blank rows, invalid dates/amounts, duplicate rows, archived default account, and >1,000-row rejection.
30. Test Settings partial-import messaging.
31. Test API atomic import behavior.
32. Export transaction CSV and full JSON bundle; verify no auth secret material is present.

### Destructive/demo

33. Confirm normal demo seed refuses a non-empty account.
34. Confirm demo reset requires replacement confirmation.
35. Confirm clear-data requires confirmation and affects only the current user.
36. Delete a disposable account and verify Firebase sign-in no longer works and finance data is removed.

### Responsive/accessibility/errors

37. Test 360px phone portrait.
38. Test phone landscape.
39. Test tablet, laptop, and wide desktop.
40. Verify no transaction/filter/form/pagination overlap or horizontal page scrolling.
41. Keyboard through navigation, forms, pagination, settings, and destructive actions.
42. Verify visible focus and touch target sizing.
43. Verify with reduced-motion preference enabled.
44. Simulate API offline/timeout/401/server error/import failure and verify useful feedback.
45. Verify all themes preserve readable contrast and finance-status meaning.

## Quality gates

Before merging/releasing:

```text
Frontend
- npm audit --audit-level=high
- npm test
- npm run typecheck
- npm run build

Backend
- pip check
- python -m compileall -q app migrations
- pytest -q on Python 3.12 and 3.14
```

CI runs these on pull requests. A green CI run plus live Firebase/Render smoke testing is the release bar.
