import { initializeApp } from 'firebase/app'
import { connectAuthEmulator, getAuth, type Auth } from 'firebase/auth'

const env = import.meta.env
const emulatorHost = (env.VITE_FIREBASE_AUTH_EMULATOR_HOST as string | undefined)?.trim()

// In emulator mode the placeholders are harmless: the emulator accepts any key and project id.
const demo = (value: string | undefined, fallback: string) => value || (emulatorHost ? fallback : undefined)
const firebaseConfig = {
  VITE_FIREBASE_API_KEY: demo(env.VITE_FIREBASE_API_KEY, 'demo-ledgerly-key'),
  VITE_FIREBASE_AUTH_DOMAIN: demo(env.VITE_FIREBASE_AUTH_DOMAIN, 'demo-ledgerly.firebaseapp.com'),
  VITE_FIREBASE_PROJECT_ID: demo(env.VITE_FIREBASE_PROJECT_ID, 'demo-ledgerly'),
  VITE_FIREBASE_APP_ID: demo(env.VITE_FIREBASE_APP_ID, 'demo-ledgerly-app'),
}

/** Names (never values) of the Firebase variables that are not set. */
export const missingFirebaseConfig = Object.entries(firebaseConfig).filter(([, value]) => !value).map(([key]) => key)
export const firebaseReady = missingFirebaseConfig.length === 0

// When not ready nothing initialises and main.tsx renders a setup screen instead of the app,
// so the non-null Auth type is never dereferenced.
let auth = undefined as unknown as Auth
if (firebaseReady) {
  const app = initializeApp({
    apiKey: firebaseConfig.VITE_FIREBASE_API_KEY,
    authDomain: firebaseConfig.VITE_FIREBASE_AUTH_DOMAIN,
    projectId: firebaseConfig.VITE_FIREBASE_PROJECT_ID,
    appId: firebaseConfig.VITE_FIREBASE_APP_ID,
  })
  auth = getAuth(app)
  if (emulatorHost) connectAuthEmulator(auth, `http://${emulatorHost}`, { disableWarnings: true })
}
export const firebaseAuth = auth
