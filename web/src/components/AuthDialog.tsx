import { useState, type FormEvent } from 'react'
import { ApiError } from '../lib/api'
import { useAuth } from '../state/auth'
import { useCatalog } from '../state/catalog'
import { useToast } from '../state/toast'
import { Modal } from './Modal'

export function AuthDialog() {
  const { dialog, closeAuth, signIn, register, demoSignIn } = useAuth()
  const { config } = useCatalog()
  const notify = useToast()
  const [mode, setMode] = useState(dialog?.mode ?? 'signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  if (!dialog) return null

  async function run(action: () => Promise<void>, welcome: string) {
    setBusy(true)
    setError('')
    try {
      await action()
      notify(welcome)
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'Something went wrong. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    if (mode === 'signin') void run(() => signIn(email, password), 'Welcome back!')
    else void run(() => register(email, password, displayName), 'Your account is ready.')
  }

  return (
    <Modal title={mode === 'signin' ? 'Sign in to CourtMate' : 'Create your account'} onClose={closeAuth} variant="dialog">
      {dialog.reason && <p className="form-hint">{dialog.reason}</p>}
      <div className="segmented" role="tablist">
        <button role="tab" aria-selected={mode === 'signin'} className={mode === 'signin' ? 'active' : ''} onClick={() => setMode('signin')}>
          Sign in
        </button>
        <button role="tab" aria-selected={mode === 'register'} className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')}>
          Create account
        </button>
      </div>
      <form className="form" onSubmit={submit}>
        {mode === 'register' && (
          <label className="field">
            <span>Name shown to other players</span>
            <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} required minLength={2} maxLength={80} autoComplete="name" />
          </label>
        )}
        <label className="field">
          <span>Email</span>
          <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required autoComplete="email" inputMode="email" />
        </label>
        <label className="field">
          <span>Password</span>
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            minLength={mode === 'register' ? 10 : 1}
            maxLength={128}
            autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
          />
          {mode === 'register' && <small>At least 10 characters.</small>}
        </label>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button className="button button-primary button-block" disabled={busy}>
          {busy ? 'Please wait…' : mode === 'signin' ? 'Sign in' : 'Create account'}
        </button>
      </form>
      {config?.demoLogin && (
        <div className="demo-login">
          <p>Just looking around? Use a demo account. Demo data is sample data, not real venues or players.</p>
          <div className="button-row">
            <button className="button button-lime" disabled={busy} onClick={() => run(() => demoSignIn('player'), 'Signed in as Demo Player.')}>
              Demo player
            </button>
            <button className="button button-ghost" disabled={busy} onClick={() => run(() => demoSignIn('operator'), 'Signed in as Demo Operator.')}>
              Demo venue operator
            </button>
          </div>
        </div>
      )}
    </Modal>
  )
}
