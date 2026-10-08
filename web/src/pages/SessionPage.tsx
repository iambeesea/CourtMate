import { ArrowLeft, CalendarDays, Clock3, MapPin, Radio, Route, ShieldCheck, Users, Wallet, Zap } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { LazyMap } from '../components/LazyMap'
import { Modal } from '../components/Modal'
import { QueuePanel } from '../components/QueuePanel'
import { SportIcon } from '../components/SportIcon'
import { Avatar, DemoBadge, ErrorState, Loading } from '../components/StateViews'
import { ApiError, api } from '../lib/api'
import { formatLongDate, formatTimeRange, placeLine, plural, priceLabel } from '../lib/format'
import { joinState, joinedMessage, spotsLabel } from '../lib/sessionText'
import type { Participant, SessionDetail } from '../lib/types'
import { useAsync } from '../lib/useAsync'
import { useAuth } from '../state/auth'
import { useCatalog } from '../state/catalog'
import { useToast } from '../state/toast'

const ELIGIBILITY = { open: '', women: 'Women', men: 'Men', mixed: 'Mixed' }

export function SessionPage() {
  const { id = '' } = useParams()
  const { user, requireAuth } = useAuth()
  const { sport: findSport } = useCatalog()
  const notify = useToast()
  const session = useAsync(() => api.session(id), [id, user?.id])
  const [busy, setBusy] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [editing, setEditing] = useState(false)
  const [reason, setReason] = useState('')

  async function run(action: () => Promise<SessionDetail>, success: string | ((updated: SessionDetail) => string)) {
    setBusy(true)
    try {
      const updated = await action()
      session.setData(updated)
      notify(typeof success === 'string' ? success : success(updated))
      return true
    } catch (error) {
      notify(error instanceof ApiError ? error.message : 'That didn’t work. Please try again.', 'error')
      session.reload()
      return false
    } finally {
      setBusy(false)
    }
  }

  if (session.error && !session.data) {
    return (
      <div className="page">
        <ErrorState error={session.error} onRetry={session.reload} />
      </div>
    )
  }
  if (!session.data) return <Loading label="Loading session…" />

  const data = session.data
  const sport = findSport(data.sport.id)
  const state = joinState(data)
  const open = data.status === 'scheduled' || data.status === 'live'
  const confirmed = data.participants.filter((entry) => entry.status === 'confirmed')
  const waitlisted = data.participants.filter((entry) => entry.status === 'waitlisted')
  const pending = data.participants.filter((entry) => entry.status === 'pending')
  const where = [data.meetupNote, placeLine(data.location), data.location.region.name].filter(Boolean).join(' · ')

  function participantRow(entry: Participant, extra?: React.ReactNode) {
    return (
      <li key={entry.id}>
        <Avatar user={entry.user} size={34} />
        <span className="queue-name">
          {entry.user.displayName}
          {entry.user.id === data.host.id && <small> · Host</small>}
        </span>
        {extra}
        {data.viewer.isHost && open && entry.user.id !== data.host.id && (
          <button
            className="button button-ghost button-small"
            disabled={busy}
            onClick={() => run(() => api.participantAction(data.id, entry.id, 'remove'), `${entry.user.displayName} was removed.`)}
          >
            Remove
          </button>
        )}
      </li>
    )
  }

  return (
    <div className="page session-page">
      <Link to="/" className="back-link">
        <ArrowLeft size={16} /> Explore
      </Link>

      <header className="session-header">
        <SportIcon sport={data.sport} size="lg" />
        <div>
          <div className="badge-line">
            <span className="sport-badge">
              {data.sport.name} · {data.kindLabel}
            </span>
            {data.status === 'live' && (
              <span className="live-badge">
                <Radio size={11} /> Live
              </span>
            )}
            {data.status === 'cancelled' && <span className="status-badge status-cancelled">Cancelled</span>}
            {data.status === 'completed' && <span className="status-badge">Finished</span>}
            {data.isDemo && <DemoBadge label="Demo session" />}
          </div>
          <h1>{data.title}</h1>
          <p className="meta-line">
            Hosted by {data.host.displayName}
            {data.community && ` · ${data.community.name}`}
          </p>
        </div>
      </header>

      {data.status === 'cancelled' && <p className="form-error">This session was cancelled{data.cancelReason ? `: ${data.cancelReason}` : '.'}</p>}

      <div className="venue-layout">
        <div className="session-main">
          <div className="fact-grid">
            <div>
              <CalendarDays size={18} />
              <span>When</span>
              <strong>{formatLongDate(data.startAt)}</strong>
              <small>
                <Clock3 size={13} /> {formatTimeRange(data.startAt, data.endAt)} (Philippine time)
              </small>
            </div>
            <div>
              <MapPin size={18} />
              <span>Where</span>
              <strong>{data.facility ? <Link to={`/venues/${data.facility.slug}`}>{data.venueName}</Link> : data.venueName}</strong>
              <small>{where}</small>
            </div>
            <div>
              <Users size={18} />
              <span>Players</span>
              <strong>
                {data.joined} of {data.capacity}
              </strong>
              <small>
                {spotsLabel(data)}
                {data.minPlayers > 1 && ` · needs ${data.minPlayers} to go ahead`}
              </small>
            </div>
            <div>
              <Wallet size={18} />
              <span>Fee</span>
              <strong>{priceLabel(data.feeCentavos)}</strong>
              <small>{data.feeCentavos ? 'Paid to the host at the session' : 'No fee'}</small>
            </div>
            <div>
              <Zap size={18} />
              <span>Level and format</span>
              <strong>{data.skillLevel}</strong>
              <small>{[data.teamFormatLabel, ELIGIBILITY[data.genderEligibility]].filter(Boolean).join(' · ') || 'Open to all'}</small>
            </div>
            {data.routeDistanceKm ? (
              <div>
                <Route size={18} />
                <span>Route</span>
                <strong>{data.routeDistanceKm} km</strong>
                <small>{data.routeName}</small>
              </div>
            ) : (
              <div>
                <ShieldCheck size={18} />
                <span>Joining</span>
                <strong>{data.joinPolicy === 'approval' ? 'Host approves' : 'Open to join'}</strong>
                <small>{data.hasVenueBooking ? 'Venue is reserved' : data.facility ? 'Venue not reserved through CourtMate' : 'Public meet-up'}</small>
              </div>
            )}
          </div>

          {data.description && <p className="session-description">{data.description}</p>}

          {open && (
            <div className="action-bar">
              {state.action === 'join' ? (
                <button
                  className="button button-primary"
                  disabled={busy}
                  onClick={() => requireAuth('Sign in to join this session.', () => void run(() => api.joinSession(data.id), joinedMessage))}
                >
                  {state.label}
                </button>
              ) : (
                <span className={`status-badge ${data.viewer.status === 'confirmed' ? 'status-confirmed' : data.viewer.status ? 'status-pending' : ''}`}>{state.label}</span>
              )}
              {data.viewer.status && (
                <button className="button button-ghost" disabled={busy} onClick={() => run(() => api.leaveSession(data.id), 'You left the session.')}>
                  {data.viewer.status === 'confirmed' ? 'Leave session' : data.viewer.status === 'waitlisted' ? 'Leave waitlist' : 'Withdraw request'}
                </button>
              )}
            </div>
          )}

          {data.viewer.isHost && open && (
            <div className="host-panel">
              <span className="eyebrow">HOST CONTROLS</span>
              <div className="button-row">
                {data.status === 'scheduled' && (
                  <button className="button button-lime" disabled={busy} onClick={() => run(() => api.sessionAction(data.id, 'start'), 'Session started. Check-in is open.')}>
                    Start session
                  </button>
                )}
                {data.status === 'live' && (
                  <button className="button button-primary" disabled={busy} onClick={() => run(() => api.sessionAction(data.id, 'complete'), 'Session finished.')}>
                    Finish session
                  </button>
                )}
                <button className="button button-ghost" disabled={busy} onClick={() => setEditing(true)}>
                  Edit details
                </button>
                <button className="button button-ghost" disabled={busy} onClick={() => setCancelling(true)}>
                  Cancel session
                </button>
              </div>
              {data.status === 'scheduled' && <p className="form-hint">You can start up to two hours before the start time. Starting opens check-in{data.queueMode !== 'none' ? ' and the queue' : ''}.</p>}
            </div>
          )}

          {pending.length > 0 && (
            <section className="people-block">
              <h3>Waiting for your decision · {pending.length}</h3>
              <ul className="queue-list">
                {pending.map((entry) => (
                  <li key={entry.id}>
                    <Avatar user={entry.user} size={34} />
                    <span className="queue-name">{entry.user.displayName}</span>
                    <button className="button button-primary button-small" disabled={busy} onClick={() => run(() => api.participantAction(data.id, entry.id, 'approve'), `${entry.user.displayName} approved.`)}>
                      Approve
                    </button>
                    <button className="button button-ghost button-small" disabled={busy} onClick={() => run(() => api.participantAction(data.id, entry.id, 'decline'), 'Request declined.')}>
                      Decline
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {data.queueMode !== 'none' && (data.status === 'live' || data.status === 'completed') && (
            <QueuePanel session={data} sport={sport} onSessionChanged={session.reload} />
          )}

          <section className="people-block">
            <h3>Going · {confirmed.length}</h3>
            {confirmed.length === 0 && <p className="form-hint">Nobody has joined yet. Be the first.</p>}
            <ul className="queue-list">{confirmed.map((entry) => participantRow(entry))}</ul>
          </section>

          {waitlisted.length > 0 && (
            <section className="people-block">
              <h3>Waitlist · {waitlisted.length}</h3>
              <p className="form-hint">When someone leaves, the first person here takes their place automatically.</p>
              <ol className="queue-list">{waitlisted.map((entry) => participantRow(entry, <small>#{entry.waitlistPosition}</small>))}</ol>
            </section>
          )}
        </div>

        <aside className="venue-aside">
          {data.latitude !== null && data.longitude !== null && (
            <LazyMap height={260} points={[{ id: data.id, latitude: data.latitude, longitude: data.longitude, title: data.venueName, subtitle: placeLine(data.location), tone: 'session' }]} />
          )}
          {data.isDemo && <small className="form-hint">Demo session: the players and the map position are sample data.</small>}
          {data.queueMode !== 'none' && data.status === 'scheduled' && (
            <div className="info-card">
              <h3>How this session runs</h3>
              <ul>
                <li>{data.queueMode === 'rotation' ? 'Rotation queue: after each game everyone goes to the back.' : 'Winner stays: the winning side keeps the court.'}</li>
                <li>
                  {plural(data.courtsInPlay, 'court')} in play{data.teamFormatLabel && `, ${data.teamFormatLabel.toLowerCase()}`}.
                </li>
                <li>Check in on arrival to enter the queue.</li>
              </ul>
            </div>
          )}
        </aside>
      </div>

      {cancelling && (
        <Modal title="Cancel this session?" onClose={() => setCancelling(false)} variant="dialog">
          <p>Everyone who joined will be told. {data.hasVenueBooking && 'The venue booking will be cancelled too.'}</p>
          <label className="field">
            <span>Reason (shared with players)</span>
            <input value={reason} onChange={(event) => setReason(event.target.value)} maxLength={300} />
          </label>
          <div className="button-row">
            <button
              className="button button-danger"
              disabled={busy}
              onClick={async () => {
                if (await run(() => api.sessionAction(data.id, 'cancel', reason.trim()), 'Session cancelled.')) setCancelling(false)
              }}
            >
              Cancel session
            </button>
            <button className="button button-ghost" onClick={() => setCancelling(false)}>
              Keep it
            </button>
          </div>
        </Modal>
      )}

      {editing && (
        <EditSession
          session={data}
          skillLevels={sport?.matchFormat.skillLevels ?? [data.skillLevel]}
          onClose={() => setEditing(false)}
          onSaved={(updated) => {
            session.setData(updated)
            setEditing(false)
            notify('Session updated.')
          }}
        />
      )}
    </div>
  )
}

function EditSession({ session, skillLevels, onClose, onSaved }: { session: SessionDetail; skillLevels: string[]; onClose: () => void; onSaved: (session: SessionDetail) => void }) {
  const [title, setTitle] = useState(session.title)
  const [capacity, setCapacity] = useState(session.capacity)
  const [skillLevel, setSkillLevel] = useState(session.skillLevel)
  const [fee, setFee] = useState(session.feeCentavos / 100)
  const [joinPolicy, setJoinPolicy] = useState(session.joinPolicy)
  const [meetupNote, setMeetupNote] = useState(session.meetupNote)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function save() {
    setBusy(true)
    setError('')
    try {
      onSaved(await api.updateSession(session.id, { title: title.trim(), capacity, skillLevel, feeCentavos: Math.round(fee * 100), joinPolicy, meetupNote: meetupNote.trim() }))
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'Could not save. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title="Edit session" onClose={onClose}>
      <div className="form">
        <label className="field">
          <span>Title</span>
          <input value={title} onChange={(event) => setTitle(event.target.value)} minLength={3} maxLength={120} />
        </label>
        <label className="field">
          <span>Player limit</span>
          <input type="number" min={Math.max(1, session.joined)} max={1000} value={capacity} onChange={(event) => setCapacity(Number(event.target.value) || session.capacity)} />
          <small>
            {session.joined} confirmed now. Raising the limit lets the waitlist in automatically.
          </small>
        </label>
        <label className="field">
          <span>Skill level</span>
          <select value={skillLevel} onChange={(event) => setSkillLevel(event.target.value)}>
            {skillLevels.map((level) => (
              <option key={level}>{level}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Fee per player (₱)</span>
          <input type="number" min={0} step={10} value={fee} onChange={(event) => setFee(Math.max(0, Number(event.target.value) || 0))} />
        </label>
        <label className="field">
          <span>Who can join</span>
          <select value={joinPolicy} onChange={(event) => setJoinPolicy(event.target.value as 'open' | 'approval')}>
            <option value="open">Anyone, first come first served</option>
            <option value="approval">I approve each request</option>
          </select>
        </label>
        <label className="field">
          <span>Meet-up note</span>
          <input value={meetupNote} onChange={(event) => setMeetupNote(event.target.value)} maxLength={500} />
        </label>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button className="button button-primary button-block" onClick={save} disabled={busy || title.trim().length < 3}>
          {busy ? 'Saving…' : 'Save changes'}
        </button>
      </div>
    </Modal>
  )
}
