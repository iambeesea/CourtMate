import { CalendarDays, Plus, Radio, Zap } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { SessionCard } from '../components/SessionCard'
import { EmptyState, ErrorState, Loading } from '../components/StateViews'
import { api } from '../lib/api'
import { formatTimeRange } from '../lib/format'
import type { Session } from '../lib/types'
import { useAsync } from '../lib/useAsync'
import { useAuth } from '../state/auth'

function merge(list: Session[] | undefined, updated: Session): Session[] {
  return (list ?? []).map((item) => (item.id === updated.id ? updated : item))
}

export function Play() {
  const { user, ready, openAuth } = useAuth()
  const [scope, setScope] = useState<'upcoming' | 'past'>('upcoming')
  const playing = useAsync(() => api.mySessions('playing', scope), [scope, user?.id], Boolean(user))
  const hosting = useAsync(() => api.mySessions('hosting', scope), [scope, user?.id], Boolean(user))

  if (!ready) return <Loading />
  if (!user) {
    return (
      <div className="page">
        <EmptyState
          icon={<Zap size={24} />}
          title="Your games live here"
          action={
            <button className="button button-primary" onClick={() => openAuth('Sign in to see your sessions and queues.')}>
              Sign in
            </button>
          }
        >
          Sessions you join or host, live queues and match results all show up in Play.
        </EmptyState>
      </div>
    )
  }

  const error = playing.error ?? hosting.error
  const hostedIds = new Set((hosting.data ?? []).map((item) => item.id))
  const joined = (playing.data ?? []).filter((item) => !hostedIds.has(item.id))
  const everything = [...(hosting.data ?? []), ...joined]
  const live = everything.filter((item) => item.status === 'live')
  const loading = (playing.loading && !playing.data) || (hosting.loading && !hosting.data)

  return (
    <div className="page">
      <div className="page-title stats-title">
        <div>
          <span className="eyebrow">YOUR GAMES</span>
          <h1>Play</h1>
          <p>Sessions you’re in, live queues, and the ones you host.</p>
        </div>
        <Link to="/host" className="button button-primary">
          <Plus size={17} /> Host a session
        </Link>
      </div>

      {live.map((item) => (
        <Link key={item.id} to={`/sessions/${item.id}`} className="live-banner">
          <span className="live-badge">
            <Radio size={12} /> Live now
          </span>
          <div>
            <strong>{item.title}</strong>
            <span>
              {item.venueName} · {formatTimeRange(item.startAt, item.endAt)}
            </span>
          </div>
          <b>{item.queueMode !== 'none' ? 'Open queue' : 'Open session'}</b>
        </Link>
      ))}

      <div className="segmented" role="tablist">
        <button role="tab" aria-selected={scope === 'upcoming'} className={scope === 'upcoming' ? 'active' : ''} onClick={() => setScope('upcoming')}>
          Upcoming
        </button>
        <button role="tab" aria-selected={scope === 'past'} className={scope === 'past' ? 'active' : ''} onClick={() => setScope('past')}>
          Past
        </button>
      </div>

      {error && !playing.data && !hosting.data ? (
        <ErrorState
          error={error}
          onRetry={() => {
            playing.reload()
            hosting.reload()
          }}
        />
      ) : loading ? (
        <Loading />
      ) : everything.length === 0 ? (
        <EmptyState
          icon={<CalendarDays size={24} />}
          title={scope === 'upcoming' ? 'Nothing lined up yet' : 'No past sessions'}
          action={
            scope === 'upcoming' ? (
              <Link to="/" className="button button-primary">
                Find a session
              </Link>
            ) : undefined
          }
        >
          {scope === 'upcoming' ? 'Join an open play or host your own and it will appear here.' : 'Sessions you have finished will appear here.'}
        </EmptyState>
      ) : (
        <>
          {(hosting.data?.length ?? 0) > 0 && (
            <section className="section-block">
              <div className="section-heading">
                <h2>Hosting</h2>
              </div>
              <div className="session-grid">
                {hosting.data?.map((item) => (
                  <SessionCard key={item.id} session={item} onChanged={(updated) => hosting.setData((current) => merge(current, updated))} />
                ))}
              </div>
            </section>
          )}
          {joined.length > 0 && (
            <section className="section-block">
              <div className="section-heading">
                <h2>{scope === 'upcoming' ? 'Joined' : 'Played'}</h2>
              </div>
              <div className="session-grid">
                {joined.map((item) => (
                  <SessionCard key={item.id} session={item} onChanged={(updated) => playing.setData((current) => merge(current, updated))} />
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  )
}
