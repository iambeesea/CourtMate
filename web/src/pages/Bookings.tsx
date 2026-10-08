import { CalendarCheck, Clock3, MapPin, Repeat } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { Modal } from '../components/Modal'
import { DemoBadge, EmptyState, ErrorState, Loading } from '../components/StateViews'
import { ApiError, api } from '../lib/api'
import { dayParts, durationLabel, formatMediumDate, formatTime, formatTimeRange, minutesBetween, priceLabel } from '../lib/format'
import type { Reservation } from '../lib/types'
import { useAsync } from '../lib/useAsync'
import { useAuth } from '../state/auth'
import { useToast } from '../state/toast'

const STATUS_LABEL: Record<Reservation['status'], string> = {
  pending: 'Awaiting venue approval',
  confirmed: 'Confirmed',
  rejected: 'Declined by venue',
  cancelled: 'Cancelled',
  completed: 'Completed',
}

const PAYMENT_LABEL: Record<Reservation['paymentStatus'], string> = {
  not_required: 'No payment needed',
  pay_at_venue: 'Pay at the venue',
  paid: 'Paid',
  refunded: 'Refunded',
}

function hasPassed(iso: string): boolean {
  return new Date(iso).getTime() < Date.now()
}

export function Bookings() {
  const { user, ready, openAuth } = useAuth()
  const notify = useToast()
  const [scope, setScope] = useState<'upcoming' | 'past'>('upcoming')
  const [cancelling, setCancelling] = useState<Reservation | null>(null)
  const [late, setLate] = useState(false)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const reservations = useAsync(() => api.reservations(scope), [scope, user?.id], Boolean(user))

  function startCancel(item: Reservation) {
    setLate(item.freeCancelUntil ? hasPassed(item.freeCancelUntil) : false)
    setCancelling(item)
  }

  async function confirmCancel() {
    if (!cancelling) return
    setBusy(true)
    try {
      const updated = await api.cancelReservation(cancelling.id, reason.trim())
      notify(updated.lateCancellation ? 'Cancelled. This was inside the venue’s cancellation window.' : 'Reservation cancelled.')
      setCancelling(null)
      setReason('')
      reservations.reload()
    } catch (error) {
      notify(error instanceof ApiError ? error.message : 'Could not cancel. Please try again.', 'error')
    } finally {
      setBusy(false)
    }
  }

  if (!ready) return <Loading />
  if (!user) {
    return (
      <div className="page">
        <EmptyState
          icon={<CalendarCheck size={24} />}
          title="Your reservations live here"
          action={
            <button className="button button-primary" onClick={() => openAuth('Sign in to see and manage your reservations.')}>
              Sign in
            </button>
          }
        >
          Sign in to book courts, fields, lanes and studios, and to see what you have coming up.
        </EmptyState>
      </div>
    )
  }

  return (
    <div className="page">
      <div className="page-title">
        <span className="eyebrow">YOUR RESERVATIONS</span>
        <h1>Bookings</h1>
        <p>Courts, fields, lanes and studios you have reserved.</p>
      </div>
      <div className="segmented" role="tablist">
        <button role="tab" aria-selected={scope === 'upcoming'} className={scope === 'upcoming' ? 'active' : ''} onClick={() => setScope('upcoming')}>
          Upcoming
        </button>
        <button role="tab" aria-selected={scope === 'past'} className={scope === 'past' ? 'active' : ''} onClick={() => setScope('past')}>
          Past and cancelled
        </button>
      </div>

      {reservations.error && !reservations.data ? (
        <ErrorState error={reservations.error} onRetry={reservations.reload} />
      ) : reservations.loading && !reservations.data ? (
        <Loading />
      ) : !reservations.data?.length ? (
        <EmptyState
          icon={<CalendarCheck size={24} />}
          title={scope === 'upcoming' ? 'Nothing booked yet' : 'No past reservations'}
          action={
            scope === 'upcoming' ? (
              <Link to="/#venues" className="button button-primary">
                Find a venue
              </Link>
            ) : undefined
          }
        >
          {scope === 'upcoming' ? 'Reserve a court, field, lane or studio and it will show up here.' : 'Finished and cancelled reservations appear here.'}
        </EmptyState>
      ) : (
        <div className="upcoming-list">
          {reservations.data.map((item) => {
            const day = dayParts(item.startAt)
            return (
              <article className="booking-card" key={item.id}>
                <div className="large-date">
                  <span>{day.weekday}</span>
                  <strong>{day.day}</strong>
                  <small>{day.month}</small>
                </div>
                <div className="booking-main">
                  <div className="badge-line">
                    <span className={`status-badge status-${item.status}`}>{STATUS_LABEL[item.status]}</span>
                    {item.sport && <span className="sport-badge">{item.sport.name}</span>}
                    {item.facility.isDemo && <DemoBadge />}
                    {item.seriesId && (
                      <span className="sport-badge">
                        <Repeat size={11} /> Weekly
                      </span>
                    )}
                  </div>
                  <h3>
                    {item.resource.name} · <Link to={`/venues/${item.facility.id}`}>{item.facility.name}</Link>
                  </h3>
                  <p className="meta-line">
                    <Clock3 size={15} /> {formatTimeRange(item.startAt, item.endAt)} · {durationLabel(minutesBetween(item.startAt, item.endAt))}
                  </p>
                  <p className="meta-line">
                    <MapPin size={15} /> {item.facility.cityName}
                  </p>
                  {item.cancelReason && <p className="meta-line">Reason: {item.cancelReason}</p>}
                </div>
                <div className="booking-side">
                  <strong>{priceLabel(item.priceCentavos)}</strong>
                  <small>{PAYMENT_LABEL[item.paymentStatus]}</small>
                  {item.canCancel && (
                    <button className="button button-ghost button-small" onClick={() => startCancel(item)}>
                      Cancel
                    </button>
                  )}
                </div>
              </article>
            )
          })}
        </div>
      )}

      {cancelling && (
        <Modal title="Cancel this reservation?" onClose={() => setCancelling(null)} variant="dialog">
          <p>
            <strong>{cancelling.resource.name}</strong> at {cancelling.facility.name}, {formatMediumDate(cancelling.startAt)} at {formatTime(cancelling.startAt)}.
          </p>
          {cancelling.freeCancelUntil && (
            <p className={late ? 'form-error' : 'form-hint'}>
              {late
                ? 'The free-cancellation window has passed. The venue will see this as a late cancellation.'
                : `Free cancellation until ${formatMediumDate(cancelling.freeCancelUntil)}, ${formatTime(cancelling.freeCancelUntil)}.`}
            </p>
          )}
          <label className="field">
            <span>Reason (optional)</span>
            <input value={reason} onChange={(event) => setReason(event.target.value)} maxLength={300} />
          </label>
          <div className="button-row">
            <button className="button button-danger" onClick={confirmCancel} disabled={busy}>
              {busy ? 'Cancelling…' : 'Cancel reservation'}
            </button>
            <button className="button button-ghost" onClick={() => setCancelling(null)}>
              Keep it
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}
