import { useState } from 'react'
import { useAuth } from '../state/auth'
import { useToast } from '../state/toast'
import { ApiError, api } from './api'
import { joinedMessage } from './sessionText'
import type { Session } from './types'

/** Join a session, asking the visitor to sign in first if needed. */
export function useJoin(onChanged: (session: Session) => void) {
  const { requireAuth } = useAuth()
  const notify = useToast()
  const [busy, setBusy] = useState(false)

  function join(session: Session) {
    requireAuth('Sign in to join this session.', async () => {
      setBusy(true)
      try {
        const updated = await api.joinSession(session.id)
        notify(joinedMessage(updated))
        onChanged(updated)
      } catch (error) {
        notify(error instanceof ApiError ? error.message : 'Could not join. Please try again.', 'error')
      } finally {
        setBusy(false)
      }
    })
  }

  return { join, busy }
}
