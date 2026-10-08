import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, getToken, handleSessionExpired, setToken } from '../lib/api'
import type { Me, TokenResponse } from '../lib/types'

type AuthMode = 'signin' | 'register'

interface AuthContextValue {
  user: Me | null
  /** False until the stored token has been checked. */
  ready: boolean
  dialog: { mode: AuthMode; reason: string } | null
  openAuth: (reason?: string, mode?: AuthMode) => void
  closeAuth: () => void
  /** Run `action` now if signed in; otherwise ask the visitor to sign in first. */
  requireAuth: (reason: string, action: () => void) => void
  signIn: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, displayName: string) => Promise<void>
  demoSignIn: (persona: 'player' | 'operator' | 'admin') => Promise<void>
  signOut: () => Promise<void>
  setUser: (user: Me) => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null)
  const [ready, setReady] = useState(() => !getToken())
  const [dialog, setDialog] = useState<AuthContextValue['dialog']>(null)
  const [pending, setPending] = useState<(() => void) | null>(null)

  useEffect(() => {
    handleSessionExpired(() => {
      setToken(null)
      setUser(null)
    })
    if (getToken()) {
      api
        .me()
        .then(setUser, () => undefined)
        .finally(() => setReady(true))
    }
    return () => handleSessionExpired(null)
  }, [])

  const accept = useCallback(
    (response: TokenResponse) => {
      setToken(response.accessToken)
      setUser(response.user)
      setDialog(null)
      if (pending) {
        // Let the signed-in state render before continuing what the visitor was doing.
        const action = pending
        setPending(null)
        window.setTimeout(action, 0)
      }
    },
    [pending],
  )

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      ready,
      dialog,
      openAuth: (reason = '', mode = 'signin') => setDialog({ mode, reason }),
      closeAuth: () => {
        setDialog(null)
        setPending(null)
      },
      requireAuth: (reason, action) => {
        if (user) action()
        else {
          setPending(() => action)
          setDialog({ mode: 'signin', reason })
        }
      },
      signIn: async (email, password) => accept(await api.login(email, password)),
      register: async (email, password, displayName) => accept(await api.register(email, password, displayName)),
      demoSignIn: async (persona) => accept(await api.demoLogin(persona)),
      signOut: async () => {
        await api.logout().catch(() => undefined)
        setToken(null)
        setUser(null)
      },
      setUser,
    }),
    [user, ready, dialog, accept],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}
