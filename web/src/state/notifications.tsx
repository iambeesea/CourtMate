import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api } from '../lib/api'
import { useAuth } from './auth'

const POLL_MS = 60000

interface NotificationsValue {
  unread: number
  refresh: () => void
}

const NotificationsContext = createContext<NotificationsValue>({ unread: 0, refresh: () => {} })

/** Keeps the unread badge roughly current while the app is open and visible. */
export function NotificationsProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const [unread, setUnread] = useState(0)
  const [tick, setTick] = useState(0)
  const userId = user?.id

  useEffect(() => {
    if (!userId) return
    const controller = new AbortController()
    api.notifications(controller.signal).then(
      (inbox) => setUnread(inbox.unread),
      () => undefined,
    )
    return () => controller.abort()
  }, [userId, tick])

  useEffect(() => {
    if (!userId) return
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') setTick((value) => value + 1)
    }, POLL_MS)
    return () => window.clearInterval(timer)
  }, [userId])

  const refresh = useCallback(() => setTick((value) => value + 1), [])
  const value = useMemo(() => ({ unread: userId ? unread : 0, refresh }), [unread, refresh, userId])
  return <NotificationsContext.Provider value={value}>{children}</NotificationsContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export const useNotifications = () => useContext(NotificationsContext)
