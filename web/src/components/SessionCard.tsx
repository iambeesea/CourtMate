import { Check, Clock3, MapPin, Radio, Route, Zap } from 'lucide-react'
import { Link } from 'react-router'
import { dayParts, formatDistance, formatTimeRange, priceLabel } from '../lib/format'
import { joinState, spotsLabel } from '../lib/sessionText'
import type { Session } from '../lib/types'
import { useJoin } from '../lib/useJoin'
import { Avatar, DemoBadge } from './StateViews'

export function SessionCard({ session, onChanged }: { session: Session; onChanged: (session: Session) => void }) {
  const { join, busy } = useJoin(onChanged)
  const state = joinState(session)
  const day = dayParts(session.startAt)
  const href = `/sessions/${session.id}`

  return (
    <article className={`session-card accent-lime ${session.status === 'live' ? 'is-live' : ''}`}>
      <div className="card-top">
        <div className="badge-line">
          <span className="sport-badge">{session.sport.name}</span>
          {session.status === 'live' && (
            <span className="live-badge">
              <Radio size={11} /> Live
            </span>
          )}
          {session.isDemo && <DemoBadge />}
        </div>
        <span className="price">{priceLabel(session.feeCentavos)}</span>
      </div>
      <Link to={href} className="session-title-row">
        <div className="date-tile">
          <span>{day.weekday}</span>
          <strong>{day.day}</strong>
        </div>
        <div>
          <h3>{session.title}</h3>
          <p>
            {session.kindLabel} · hosted by {session.host.displayName}
          </p>
        </div>
      </Link>
      <div className="session-meta">
        <span>
          <Clock3 size={16} />
          {formatTimeRange(session.startAt, session.endAt)}
        </span>
        <span>
          <MapPin size={16} />
          {session.venueName} · {session.location.city.name}
          {session.distanceKm !== null && ` · ${formatDistance(session.distanceKm)}`}
        </span>
        {session.routeDistanceKm ? (
          <span>
            <Route size={16} />
            {session.routeName || 'Route'} · {session.routeDistanceKm} km
          </span>
        ) : (
          <span>
            <Zap size={16} />
            {[session.skillLevel, session.teamFormatLabel].filter(Boolean).join(' · ')}
          </span>
        )}
      </div>
      <div className="players-row">
        <div className="avatar-stack">
          {session.players.slice(0, 5).map((player) => (
            <Avatar key={player.id} user={player} size={28} />
          ))}
        </div>
        <span>{spotsLabel(session)}</span>
      </div>
      <div className="capacity-bar" role="img" aria-label={`${session.joined} of ${session.capacity} places taken`}>
        <span style={{ width: `${Math.min(100, (session.joined / session.capacity) * 100)}%` }} />
      </div>
      {state.action === 'join' ? (
        <button className="join-button" onClick={() => join(session)} disabled={busy}>
          {busy ? 'Joining…' : state.label}
        </button>
      ) : (
        <Link to={href} className={`join-button ${state.joined ? 'joined' : 'muted'}`}>
          {state.joined && session.viewer.status === 'confirmed' && <Check size={17} />} {state.label}
        </Link>
      )}
    </article>
  )
}
