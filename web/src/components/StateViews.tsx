import { CloudOff, RefreshCw } from 'lucide-react'
import type { ReactNode } from 'react'
import type { ApiError } from '../lib/api'

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="state-view" role="status">
      <span className="spinner" aria-hidden="true" />
      <p>{label}</p>
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  return (
    <div className="state-view state-error" role="alert">
      <span className="state-icon">
        <CloudOff size={24} />
      </span>
      <h3>{error.isNetwork ? 'Can’t reach CourtMate' : 'Something went wrong'}</h3>
      <p>{error.isNetwork ? 'The server may be waking up, or you may be offline. Nothing has been changed.' : error.message}</p>
      {onRetry && (
        <button className="button button-primary" onClick={onRetry}>
          <RefreshCw size={16} /> Try again
        </button>
      )}
    </div>
  )
}

export function EmptyState({ icon, title, children, action }: { icon: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="state-view">
      <span className="state-icon">{icon}</span>
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action}
    </div>
  )
}

export function DemoBadge({ label = 'Demo' }: { label?: string }) {
  return (
    <span className="demo-badge" title="Demonstration data. Not a real venue, price or schedule.">
      {label}
    </span>
  )
}

/** Navy text on light avatar colours, white on dark ones. */
function readableOn(hex: string): string {
  const value = hex.replace('#', '')
  if (value.length < 6) return '#fff'
  const [red, green, blue] = [0, 2, 4].map((offset) => parseInt(value.slice(offset, offset + 2), 16))
  return red * 0.299 + green * 0.587 + blue * 0.114 > 165 ? '#1f3b73' : '#fff'
}

export function Avatar({ user, size = 38 }: { user: { initials: string; avatarColor: string }; size?: number }) {
  return (
    <span
      className="avatar"
      style={{ background: user.avatarColor, color: readableOn(user.avatarColor), width: size, height: size, fontSize: Math.max(11, size * 0.34) }}
    >
      {user.initials}
    </span>
  )
}
