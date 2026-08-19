import { FormEvent, useEffect, useState } from 'react'
import {
  createUserWithEmailAndPassword,
  reload,
  sendEmailVerification,
  sendPasswordResetEmail,
  signInWithEmailAndPassword,
} from 'firebase/auth'
import type { AuthSuccess } from './api'
import { firebaseAuth } from './firebase'

type AuthMode = 'login' | 'register' | 'forgot' | 'check-email'

type Props = {
  onAuthenticated: (result: AuthSuccess) => void
  initialMessage?: string
}

function friendlyAuthError(error: unknown) {
  const code = typeof error === 'object' && error && 'code' in error ? String((error as { code?: string }).code) : ''
  if (code.includes('invalid-credential') || code.includes('wrong-password') || code.includes('user-not-found')) return 'Invalid email or password.'
  if (code.includes('email-already-in-use')) return 'An account with that email already exists.'
  if (code.includes('weak-password')) return 'Choose a stronger password.'
  if (code.includes('too-many-requests')) return 'Too many attempts. Please wait a moment and try again.'
  if (code.includes('network-request-failed')) return 'Unable to reach the authentication service. Check your connection and try again.'
  return error instanceof Error ? error.message.replace(/^Firebase:\s*/i, '') : 'Authentication failed.'
}

function AuthScreen({ onAuthenticated, initialMessage = '' }: Props) {
  const [mode, setMode] = useState<AuthMode>('login')
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState(initialMessage)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    void firebaseAuth.authStateReady().then(async () => {
      const user = firebaseAuth.currentUser
      if (!user || localStorage.getItem('ledgerly_token')) return
      if (!user.emailVerified) {
        setEmail(user.email || '')
        setMode('check-email')
        setMessage('Verify your email address, then continue into Ledgerly.')
      }
    })
  }, [])

  const completeSignIn = async () => {
    const user = firebaseAuth.currentUser
    if (!user) throw new Error('Authentication session was not available.')
    await reload(user)
    if (!user.emailVerified) {
      setEmail(user.email || '')
      setMode('check-email')
      setMessage('Check your inbox and verify your email before continuing.')
      return
    }
    const accessToken = await user.getIdToken(true)
    localStorage.setItem('ledgerly_token', accessToken)
    onAuthenticated({ accessToken, user: { email: user.email || '', emailVerified: true } })
  }

  const switchMode = (next: AuthMode) => {
    setMode(next)
    setError('')
    setMessage('')
  }

  const authenticate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const submittedEmail = String(form.get('email') || '').trim()
    const password = String(form.get('password') || '')
    const confirm = String(form.get('confirmPassword') || '')
    if (mode === 'register' && password !== confirm) return setError('Passwords do not match.')

    try {
      setBusy(true)
      setError('')
      setMessage('')
      if (mode === 'register') {
        const credential = await createUserWithEmailAndPassword(firebaseAuth, submittedEmail, password)
        await sendEmailVerification(credential.user)
        setEmail(credential.user.email || submittedEmail)
        setMode('check-email')
        setMessage('Account created. Firebase sent a verification email to your inbox.')
        return
      }

      const credential = await signInWithEmailAndPassword(firebaseAuth, submittedEmail, password)
      if (!credential.user.emailVerified) {
        setEmail(credential.user.email || submittedEmail)
        setMode('check-email')
        setMessage('Your account exists, but your email still needs to be verified.')
        return
      }
      await completeSignIn()
    } catch (err) {
      setError(friendlyAuthError(err))
    } finally {
      setBusy(false)
    }
  }

  const forgotPassword = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const submittedEmail = String(new FormData(event.currentTarget).get('email') || '').trim()
    try {
      setBusy(true)
      setError('')
      await sendPasswordResetEmail(firebaseAuth, submittedEmail)
      setMessage('If an account can receive password-reset email at that address, Firebase has sent the reset instructions.')
    } catch (err) {
      const code = typeof err === 'object' && err && 'code' in err ? String((err as { code?: string }).code) : ''
      if (code.includes('user-not-found') || code.includes('invalid-email')) {
        setMessage('If an account can receive password-reset email at that address, Firebase has sent the reset instructions.')
      } else setError(friendlyAuthError(err))
    } finally { setBusy(false) }
  }

  const resendVerification = async () => {
    const user = firebaseAuth.currentUser
    if (!user) {
      setMessage('Sign in again first, then you can resend the verification email.')
      return switchMode('login')
    }
    try {
      setBusy(true)
      setError('')
      await sendEmailVerification(user)
      setMessage(`Verification email sent to ${user.email || email}.`)
    } catch (err) {
      setError(friendlyAuthError(err))
    } finally { setBusy(false) }
  }

  const checkVerification = async () => {
    try {
      setBusy(true)
      setError('')
      await completeSignIn()
    } catch (err) {
      setError(friendlyAuthError(err))
    } finally { setBusy(false) }
  }

  const title = mode === 'register' ? 'Create your account'
    : mode === 'forgot' ? 'Reset your password'
      : mode === 'check-email' ? 'Check your email'
        : 'Welcome back'

  return <main className="auth-shell">
    <section className="brand-panel">
      <div className="logo-mark">L</div>
      <h1>Ledgerly</h1>
      <p>Personal finance. Full control. Smarter decisions.</p>
      <div className="brand-proof">
        <div><strong>01</strong><span>Track every dollar</span></div>
        <div><strong>02</strong><span>Build realistic budgets</span></div>
        <div><strong>03</strong><span>Turn goals into progress</span></div>
      </div>
    </section>
    <section className="auth-wrap">
      <div className="auth-card">
        <span className="eyebrow">WELCOME TO LEDGERLY</span>
        <h2>{title}</h2>
        <p>{mode === 'forgot' ? 'Enter your account email and Firebase will send secure reset instructions.' : mode === 'check-email' ? `Verify ${email || 'your email address'} before entering Ledgerly.` : 'Build a clearer picture of your money.'}</p>

        {message && <div className="success-message" role="status">{message}</div>}
        {error && <div className="error" role="alert">{error}</div>}

        {(mode === 'login' || mode === 'register') && <form onSubmit={authenticate}>
          <label>Email<input name="email" type="email" autoComplete="email" required maxLength={180} defaultValue={email} placeholder="you@example.com" /></label>
          <label>Password<input name="password" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} minLength={8} maxLength={128} required placeholder="Your password" /></label>
          {mode === 'register' && <label>Confirm password<input name="confirmPassword" type="password" autoComplete="new-password" minLength={8} maxLength={128} required placeholder="Repeat your password" /></label>}
          <button className="primary" type="submit" disabled={busy}>{busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}</button>
        </form>}

        {mode === 'forgot' && <form onSubmit={forgotPassword}>
          <label>Email<input name="email" type="email" autoComplete="email" required maxLength={180} defaultValue={email} placeholder="you@example.com" /></label>
          <button className="primary" type="submit" disabled={busy}>{busy ? 'Sending…' : 'Send reset email'}</button>
        </form>}

        {mode === 'check-email' && <div className="auth-actions">
          <button className="primary" type="button" disabled={busy} onClick={checkVerification}>{busy ? 'Checking…' : 'I verified my email — continue'}</button>
          <button className="secondary" type="button" disabled={busy} onClick={resendVerification}>Resend verification email</button>
          <button className="text-button compact-link" type="button" onClick={() => switchMode('login')}>Back to sign in</button>
        </div>}

        {mode === 'login' && <>
          <button className="text-button" type="button" onClick={() => switchMode('forgot')}>Forgot your password?</button>
          <button className="text-button compact-link" type="button" onClick={() => switchMode('register')}>Need an account? Register</button>
        </>}
        {mode === 'register' && <button className="text-button" type="button" onClick={() => switchMode('login')}>Already registered? Sign in</button>}
        {mode === 'forgot' && <button className="text-button" type="button" onClick={() => switchMode('login')}>Back to sign in</button>}
      </div>
    </section>
  </main>
}

export default AuthScreen
