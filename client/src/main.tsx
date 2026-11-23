import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import ThemeSwitcher from './ThemeSwitcher'
import { installTransactionTextLimits } from './inputGuardrails'
import { installTransactionPagination } from './transactionPagination'
import { installMobileNavigation } from './mobileNavigation'
import { firebaseReady, missingFirebaseConfig } from './firebase'
import './styles.css'
import './consumer.css'
import './themes.css'
import './guardrails.css'
import './pagination.css'
import './mobileNavigation.css'
import './professional.css'
import './showcase-design.css'

installTransactionTextLimits()
installTransactionPagination()
installMobileNavigation()

function NotConfigured() {
  return <main className="auth-shell">
    <section className="auth-wrap">
      <div className="auth-card" role="alert" aria-labelledby="setup-title">
        <span className="eyebrow">SETUP REQUIRED</span>
        <h2 id="setup-title">Ledgerly isn't configured</h2>
        <p>These Firebase environment variables are missing:</p>
        <ul>{missingFirebaseConfig.map((name) => <li key={name}><code>{name}</code></li>)}</ul>
        <p>See <code>docs/FIREBASE_SETUP.md</code> for setup, or set <code>VITE_FIREBASE_AUTH_EMULATOR_HOST</code> to run against the local Auth emulator.</p>
      </div>
    </section>
  </main>
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {firebaseReady ? <><App /><ThemeSwitcher /></> : <NotConfigured />}
  </React.StrictMode>,
)
