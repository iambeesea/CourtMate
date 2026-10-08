import { plural } from './format'
import type { Match, Session } from './types'

export interface JoinState {
  label: string
  /** What tapping the button does. `view` opens the session instead of changing anything. */
  action: 'join' | 'view'
  joined: boolean
}

export function joinState(session: Session): JoinState {
  const { viewer } = session
  if (session.status === 'cancelled') return { label: 'Cancelled', action: 'view', joined: false }
  if (session.status === 'completed') return { label: 'Finished', action: 'view', joined: false }
  if (viewer.isHost) return { label: 'Manage session', action: 'view', joined: true }
  if (viewer.status === 'confirmed') return { label: 'Joined', action: 'view', joined: true }
  if (viewer.status === 'waitlisted') return { label: `On the waitlist · #${viewer.waitlistPosition ?? '–'}`, action: 'view', joined: true }
  if (viewer.status === 'pending') return { label: 'Waiting for the host', action: 'view', joined: true }
  if (session.joinPolicy === 'approval') return { label: 'Request to join', action: 'join', joined: false }
  return { label: session.spotsLeft > 0 ? 'Join' : 'Join waitlist', action: 'join', joined: false }
}

export function joinedMessage(session: Session): string {
  if (session.viewer.status === 'pending') return 'Request sent to the host.'
  if (session.viewer.status === 'waitlisted') return `You’re on the waitlist (#${session.viewer.waitlistPosition ?? '–'}).`
  return 'Your spot is confirmed!'
}

export function spotsLabel(session: Session): string {
  if (session.spotsLeft > 0) return `${plural(session.spotsLeft, 'spot')} left`
  return session.waitlist ? `Full · ${session.waitlist} waiting` : 'Full'
}

export function sideNames(match: Match, side: 1 | 2): string {
  return match.players
    .filter((player) => player.side === side)
    .map((player) => player.user.displayName)
    .join(' & ')
}

export function scoreLine(match: Match): string {
  if (match.score?.games?.length) return match.score.games.map(([first, second]) => `${first}–${second}`).join(', ')
  if (match.score?.totals) return `${match.score.totals[0]}–${match.score.totals[1]}`
  return match.isDraw ? 'Draw' : ''
}
