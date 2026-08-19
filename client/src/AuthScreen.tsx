import { FormEvent, useEffect, useState } from 'react'
import { api, ApiError, type AuthSuccess } from './api'

type AuthMode = 'login' | 'register' | 'forgot' | 'check-email' | 'reset'

type Props = {
  onAuthenticated: (result: AuthSuccess) => void
  initialMessage?: string
}

function AuthScreen({ onAuthenticated, initialMessage = '' }: Props) {
  const params = new URLSearchParams(window.location.search)
  const verifyToken = params.get('verify') || ''
  const resetToken = params.get('reset') || ''
  const [mode, setMode] = useState<AuthMode>(resetToken ? 'reset' : 'login')
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState(initialMessage)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(Boolean(verifyToken))

  const cleanAuthQuery = () => {
    const url = new URL(window.location.href)
    url.searchParams.delete('verify')
    url.searchParams.delete('reset')
    window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`)
  }

  useEffect(() => {
    if (!verifyToken) return
    let active = true
    api.verifyEmail(verifyToken)
      .then(result => {
        if (!active) return
        localStorage.setItem('ledgerly_token', result.accessToken)
        cleanAuthQuery()
        onAuthenticated(result)
      })
      .catch(err => {
        if (!active) return
        cleanAuthQuery()
        setMode('login')
        setError(err instanceof Error ? err.message : 'Unable to verify this email address.')
      })
      .finally(() => { if (active) setBusy(false) })
    return () => { active = false }
  }, [verifyToken, onAuthenticated])

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
    if (mode === 'register' && password !== confirm) {
      setError('Passwords do not match.')
      return
    }

    try {
      setBusy(true)
      setError('')
      setMessage('')
      if (mode === 'register') {
        const result = await api.register(submittedEmail, password)
        if ('verificationRequired' in result) {
          setEmail(result.email)
          setMode('check-email')
          setMessage(result.message)
          return
        }
        localStorage.setItem('ledgerly_token', result.accessToken)
        onAuthenticated(result)
        return
      }

      const result = await api.login(submittedEmail, password)
      localStorage.setItem('ledgerly_token', result.accessToken)
      onAuthenticated(result)
    } catch (err) {
      if (err instanceof ApiError && err.code === 'email_unverified') {
        const unverifiedEmail = typeof err.details.email === 'string' ? err.details.email : submittedEmail
        setEmail(unverifiedEmail)
        setMode('check-email')
        setMessage('Your account exists, but the email address still needs to be verified.')
      } else {
        setError(err instanceof Error ? err.message : 'Authentication failed.')
      }
    } finally {
      setBusy(false)
    }
  }

  const forgotPassword = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const submittedEmail = String(form.get('email') || '').trim()
    try {
      setBusy(true)
      setError('')
      const result = await api.forgotPassword(submittedEmail)
      setMessage(result.message)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to request a password reset.')
    } finally { setBusy(false) }
  }

  const resendVerification = async () => {
    if (!email) return switchMode('login')
    try {
      setBusy(true)
      setError('')
      const result = await api.resendVerification(email)
      setMessage(result.message)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to resend verification.')
    } finally { setBusy(false) }
  }

  const resetPassword = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const password = String(form.get('password') || '')
    const confirm = String(form.get('confirmPassword') || '')
    if (password !== confirm) {
      setError('Passwords do not match.')
      return
    }
    try {
      setBusy(true)
      setError('')
      await api.resetPassword(resetToken, password)
      cleanAuthQuery()
      setMode('login')
      setMessage('Password updated. You can sign in with your new password.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to reset your password.')
    } finally { setBusy(false) }
  }

  const title = mode === 'register' ? 'Create your account'
    : mode === 'forgot' ? 'Reset your password'
      : mode === 'check-email' ? 'Check your email'
        : mode === 'reset' ? 'Choose a new password'
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
        <h2>{busy && verifyToken ? 'Verifying your email…' : title}</h2>
        <p>{mode === 'forgot' ? 'Enter your account email and we’ll send a secure reset link.' : mode === 'check-email' ? `We sent a verification link to ${email || 'your email address'}.` : mode === 'reset' ? 'Use at least 10 characters with a letter and a number.' : 'Build a clearer picture of your money.'}</p>

        {message && <div className="success-message" role="status">{message}</div>}
        {error && <div className="error" role="alert">{error}</div>}

        {busy && verifyToken ? <div className="loading compact"><span className="spinner" />Confirming verification link…</div> : <>
          {(mode === 'login' || mode === 'register') && <form onSubmit={authenticate}>
            <label>Email<input name="email" type="email" autoComplete="email" required maxLength={180} defaultValue={email} placeholder="you@example.com" /></label>
            <label>Password<input name="password" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} minLength={10} maxLength={128} required placeholder="10+ characters, letter + number" /></label>
            {mode === 'register' && <label>Confirm password<input name="confirmPassword" type="password" autoComplete="new-password" minLength={10} maxLength={128} required placeholder="Repeat your password" /></label>}
            <button className="primary" type="submit" disabled={busy}>{busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}</button>
          </form>}

          {mode === 'forgot' && <form onSubmit={forgotPassword}>
            <label>Email<input name="email" type="email" autoComplete="email" required maxLength={180} defaultValue={email} placeholder="you@example.com" /></label>
            <button className="primary" type="submit" disabled={busy}>{busy ? 'Sending…' : 'Send reset link'}</button>
          </form>}

          {mode === 'reset' && <form onSubmit={resetPassword}>
            <label>New password<input name="password" type="password" autoComplete="new-password" minLength={10} maxLength={128} required placeholder="10+ characters, letter + number" /></label>
            <label>Confirm new password<input name="confirmPassword" type="password" autoComplete="new-password" minLength={10} maxLength={128} required placeholder="Repeat your password" /></label>
            <button className="primary" type="submit" disabled={busy}>{busy ? 'Updating…' : 'Update password'}</button>
          </form>}

          {mode === 'check-email' && <div className="auth-actions">
            <button className="primary" type="button" disabled={busy || !email} onClick={resendVerification}>{busy ? 'Sending…' : 'Resend verification email'}</button>
            <button className="secondary" type="button" onClick={() => switchMode('login')}>Back to sign in</button>
          </div>}

          {mode === 'login' && <>
            <button className="text-button" type="button" onClick={() => switchMode('forgot')}>Forgot your password?</button>
            <button className="text-button compact-link" type="button" onClick={() => switchMode('register')}>Need an account? Register</button>
          </>}
          {mode === 'register' && <button className="text-button" type="button" onClick={() => switchMode('login')}>Already registered? Sign in</button>}
          {mode === 'forgot' && <button className="text-button" type="button" onClick={() => switchMode('login')}>Back to sign in</button>}
        </>}
      </div>
    </section>
  </main>
}

export default AuthScreen
