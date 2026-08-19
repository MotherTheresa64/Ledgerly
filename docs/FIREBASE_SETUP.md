# Firebase Authentication setup

Ledgerly uses Firebase Authentication for identity and keeps all finance data in PostgreSQL on Render.

## 1. Create the Firebase project

1. Open the Firebase console and create a project named `Ledgerly` (or another name you prefer).
2. Google Analytics is optional for Ledgerly authentication and can be skipped.
3. In the project overview, add a **Web app** and name it `Ledgerly Web`.
4. Copy the Firebase configuration values shown after registration.

Ledgerly needs these client values:

```text
VITE_FIREBASE_API_KEY
VITE_FIREBASE_AUTH_DOMAIN
VITE_FIREBASE_PROJECT_ID
VITE_FIREBASE_APP_ID
```

The web Firebase configuration is not a server credential. Firebase expects these values to be used by the browser SDK.

## 2. Enable Email/Password Authentication

In Firebase Console:

1. Open **Authentication**.
2. Open **Sign-in method**.
3. Enable **Email/Password**.
4. Save.

Ledgerly uses Firebase for:

- account creation
- sign-in
- email verification
- password reset
- password changes
- reauthentication before destructive account actions

## 3. Set authentication policy

Recommended consumer settings:

- Require a password of at least 8 characters or stronger.
- Enable email enumeration protection if available for the project.
- Keep Ledgerly's backend setting `FIREBASE_REQUIRE_VERIFIED_EMAIL=true` so unverified accounts cannot access finance data.

Firebase sends the verification and password-reset messages. Custom email branding/domain configuration can be added later without changing Ledgerly's API architecture.

## 4. Add authorized domains

Under **Authentication → Settings → Authorized domains**, ensure these are authorized:

```text
localhost
ledgerly-web-knmt.onrender.com
```

Add any future custom Ledgerly domain here as well.

## 5. Create the backend service-account credential

The Flask API verifies Firebase ID tokens with the Firebase Admin SDK.

In Firebase Console:

1. Open **Project settings**.
2. Open **Service accounts**.
3. Choose **Firebase Admin SDK**.
4. Generate a new private key.
5. Keep the downloaded JSON file private. Never commit it to GitHub.

For Render, convert the JSON file to a single-line JSON value and store the entire value as:

```text
FIREBASE_SERVICE_ACCOUNT_JSON
```

Also set:

```text
FIREBASE_PROJECT_ID=<your Firebase project id>
FIREBASE_REQUIRE_VERIFIED_EMAIL=true
```

## 6. Configure the Render static frontend

On `ledgerly-web`, set:

```text
VITE_API_URL=https://ledgerly-api-4uur.onrender.com/api
VITE_FIREBASE_API_KEY=<apiKey from Firebase Web app>
VITE_FIREBASE_AUTH_DOMAIN=<authDomain from Firebase Web app>
VITE_FIREBASE_PROJECT_ID=<projectId from Firebase Web app>
VITE_FIREBASE_APP_ID=<appId from Firebase Web app>
```

Vite reads these values during the frontend build, so changing one requires a new static-site deploy.

## 7. Configure the Render API

On `ledgerly-api`, keep the existing database and CORS configuration and add:

```text
FIREBASE_PROJECT_ID=<your Firebase project id>
FIREBASE_SERVICE_ACCOUNT_JSON=<single-line private service-account JSON>
FIREBASE_REQUIRE_VERIFIED_EMAIL=true
```

The service-account value is privileged. Do not place it in the frontend, repository, screenshots, or chat messages.

## 8. Migration behavior

Ledgerly preserves the existing PostgreSQL finance schema.

When a verified Firebase user calls the API for the first time:

1. Flask verifies the Firebase ID token.
2. Ledgerly looks for a user already mapped to that Firebase UID.
3. If none exists, Ledgerly checks for an existing local Ledgerly record with the same verified email.
4. If found, that existing record is linked to the Firebase UID so its transactions, budgets, goals, and account history remain intact.
5. Otherwise a new Ledgerly user record is created.

The old password hash column remains only because the deployed PostgreSQL table already has a non-null legacy column. New user credentials are never stored or validated by Ledgerly.

## 9. Production smoke test

After deployment:

1. Register a fresh email address.
2. Confirm Firebase sends a verification message.
3. Verify the email.
4. Enter Ledgerly and load demo data.
5. Refresh and confirm data persists.
6. Sign out and confirm protected data is no longer visible.
7. Sign back in.
8. Use **Forgot password** and confirm the Firebase reset message arrives.
9. Change the password from Ledgerly Settings and confirm the old password no longer works.
10. Create a transaction, budget, and goal and confirm normal CRUD behavior.
11. Test the live layout on desktop and a phone at native zoom.
12. Delete a disposable test account and confirm both the Ledgerly data and Firebase account are removed.

## Security notes

- Browser requests send Firebase ID tokens over HTTPS in the `Authorization` header.
- Flask validates ID-token signatures, expiry, revocation state, Firebase project, and verified-email status before resolving finance ownership.
- The Firebase service-account private key is backend-only.
- Financial data remains in PostgreSQL and is always queried by Ledgerly's internal user id after Firebase authentication succeeds.
