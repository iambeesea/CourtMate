import { ArrowLeft, CalendarClock, Clock3, MapPin, ShieldCheck, Users } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'
import { LazyMap } from '../components/LazyMap'
import { Modal } from '../components/Modal'
import { SportIcon } from '../components/SportIcon'
import { DemoBadge, ErrorState, Loading } from '../components/StateViews'
import { ApiError, api } from '../lib/api'
import {
  addDays,
  dateKey,
  durationLabel,
  formatTime,
  formatTimeRange,
  keyParts,
  minutesBetween,
  peso,
  placeLine,
  priceLabel,
  relativeDayLabel,
  weekdayOf,
} from '../lib/format'
import type { FacilityDetail, OpeningHours, ResourceInfo, Slot } from '../lib/types'
import { useAsync } from '../lib/useAsync'
import { useAuth } from '../state/auth'
import { useToast } from '../state/toast'

const SHORT_DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

/** Collapse runs of days with identical hours: "Mon – Sun · 6:00 AM – 10:00 PM". */
function groupHours(hours: OpeningHours[]): string[] {
  const byDay = new Map(hours.map((item) => [item.weekday, `${item.openLabel} – ${item.closeLabel}`]))
  const lines: string[] = []
  let start = 0
  while (start < 7) {
    let end = start
    while (end + 1 < 7 && byDay.get(end + 1) === byDay.get(start)) end += 1
    const days = start === end ? SHORT_DAYS[start] : `${SHORT_DAYS[start]} – ${SHORT_DAYS[end]}`
    lines.push(`${days} · ${byDay.get(start) ?? 'Closed'}`)
    start = end + 1
  }
  return lines
}

interface Selection {
  resource: ResourceInfo
  slots: Slot[]
  from: number
  to: number
}

function selectionSummary(selection: Selection) {
  const chosen = selection.slots.slice(selection.from, selection.to + 1)
  const startAt = chosen[0].startAt
  const endAt = chosen[chosen.length - 1].endAt
  return { startAt, endAt, minutes: minutesBetween(startAt, endAt), price: chosen.reduce((total, slot) => total + slot.priceCentavos, 0) }
}

export function Venue() {
  const { id = '' } = useParams()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const notify = useToast()
  const { requireAuth } = useAuth()
  const today = dateKey()

  const facility = useAsync(() => api.facility(id), [id])
  const [sportId, setSportId] = useState(params.get('sport') ?? '')
  const [date, setDate] = useState(today)
  const [selection, setSelection] = useState<Selection | null>(null)
  const [confirming, setConfirming] = useState(false)
  const availability = useAsync(() => api.availability(id, date, sportId || undefined), [id, date, sportId])

  const days = useMemo(() => {
    const count = Math.min(14, (facility.data?.bookingRules.maxAdvanceDays ?? 14) + 1)
    return Array.from({ length: count }, (_, index) => addDays(today, index))
  }, [today, facility.data])

  if (facility.error) {
    return (
      <div className="page">
        <ErrorState error={facility.error} onRetry={facility.reload} />
      </div>
    )
  }
  if (!facility.data) return <Loading label="Loading venue…" />

  const venue = facility.data
  const rules = venue.bookingRules
  const openDays = new Set(venue.hours.map((item) => item.weekday))
  const summary = selection ? selectionSummary(selection) : null
  const tooShort = summary ? summary.minutes < rules.minBookingMinutes : false

  // A changed day or sport invalidates whatever was picked.
  function chooseDate(key: string) {
    setDate(key)
    setSelection(null)
  }

  function chooseSport(value: string) {
    setSportId(value)
    setSelection(null)
  }

  function pick(resource: ResourceInfo, slots: Slot[], index: number) {
    if (slots[index].status !== 'available') return
    setSelection((current) => {
      if (!current || current.resource.id !== resource.id) return { resource, slots, from: index, to: index }
      if (index === current.from && current.from === current.to) return null
      const extendsRange = index > current.to && slots.slice(current.from, index + 1).every((slot) => slot.status === 'available')
      const minutes = extendsRange ? minutesBetween(slots[current.from].startAt, slots[index].endAt) : 0
      if (extendsRange && minutes <= rules.maxBookingMinutes) return { ...current, slots, to: index }
      if (extendsRange) notify(`The longest booking here is ${durationLabel(rules.maxBookingMinutes)}.`, 'error')
      return { resource, slots, from: index, to: index }
    })
  }

  return (
    <div className="page venue-page">
      <Link to="/" className="back-link">
        <ArrowLeft size={16} /> Explore
      </Link>

      <header className="venue-header">
        <div>
          <div className="badge-line">
            {venue.isDemo && <DemoBadge label="Demo venue" />}
            {venue.verificationStatus === 'verified' && !venue.isDemo && (
              <span className="status-badge status-confirmed">
                <ShieldCheck size={12} /> Verified
              </span>
            )}
          </div>
          <h1>{venue.name}</h1>
          <p className="meta-line">
            <MapPin size={16} /> {[venue.addressLine, placeLine(venue.location), venue.location.region.name].filter(Boolean).join(' · ')}
          </p>
          {venue.description && <p className="venue-description">{venue.description}</p>}
        </div>
      </header>

      <div className="venue-layout">
        <section className="venue-booking">
          <div className="section-heading">
            <div>
              <span className="eyebrow">RESERVE</span>
              <h2>Pick a time</h2>
            </div>
          </div>

          {venue.sports.length > 1 && (
            <div className="filters" role="tablist" aria-label="Sport">
              <button role="tab" aria-selected={!sportId} className={!sportId ? 'active' : ''} onClick={() => chooseSport('')}>
                All
              </button>
              {venue.sports.map((sport) => (
                <button key={sport.id} role="tab" aria-selected={sportId === sport.id} className={sportId === sport.id ? 'active' : ''} onClick={() => chooseSport(sport.id)}>
                  <SportIcon sport={sport} size="sm" /> {sport.name}
                </button>
              ))}
            </div>
          )}

          <div className="day-strip" role="tablist" aria-label="Date">
            {days.map((key) => {
              const parts = keyParts(key)
              const closed = !openDays.has(weekdayOf(key))
              return (
                <button key={key} role="tab" aria-selected={date === key} className={`day-chip ${date === key ? 'active' : ''} ${closed ? 'closed' : ''}`} onClick={() => chooseDate(key)}>
                  <span>{key === today ? 'TODAY' : parts.weekday}</span>
                  <strong>{parts.day}</strong>
                  <small>{closed ? 'Closed' : parts.month}</small>
                </button>
              )
            })}
          </div>

          {availability.error && !availability.data ? (
            <ErrorState error={availability.error} onRetry={availability.reload} />
          ) : !availability.data ? (
            <Loading label="Checking availability…" />
          ) : !availability.data.isOpen ? (
            <p className="notice">Closed on {relativeDayLabel(date, today)}. Pick another day.</p>
          ) : (
            <div className={`resource-list ${availability.loading ? 'is-refreshing' : ''}`}>
              {availability.data.resources.map(({ resource, slots }) => {
                const free = slots.filter((slot) => slot.status === 'available').length
                return (
                  <article key={resource.id} className="resource-row">
                    <div className="resource-head">
                      <div>
                        <h3>{resource.name}</h3>
                        <p>
                          {resource.resourceType.name} · <Users size={13} /> up to {resource.capacity} · {durationLabel(resource.slotMinutes)} slots
                          {resource.childIds.length > 0 && ' · uses every section'}
                        </p>
                      </div>
                      <strong>{resource.hourlyRateCentavos ? `${peso(resource.hourlyRateCentavos)}/hr` : 'Free'}</strong>
                    </div>
                    {free === 0 ? (
                      <p className="form-hint">No open times on this day.</p>
                    ) : (
                      <div className="slot-row">
                        {slots.map((slot, index) => {
                          const chosen = selection?.resource.id === resource.id && index >= selection.from && index <= selection.to
                          return (
                            <button
                              key={slot.startAt}
                              className={`slot slot-${slot.status} ${chosen ? 'chosen' : ''}`}
                              disabled={slot.status !== 'available'}
                              aria-pressed={chosen}
                              title={slot.status === 'available' ? priceLabel(slot.priceCentavos) : slot.status === 'closed' ? 'Not open for booking' : slot.status}
                              onClick={() => pick(resource, slots, index)}
                            >
                              {formatTime(slot.startAt)}
                            </button>
                          )
                        })}
                      </div>
                    )}
                  </article>
                )
              })}
              {availability.data.resources.length === 0 && <p className="notice">Nothing here is set up for that sport.</p>}
              <p className="slot-legend">
                <span className="slot-key slot-available" /> Open <span className="slot-key slot-booked" /> Booked <span className="slot-key slot-blocked" /> Unavailable
              </p>
            </div>
          )}
        </section>

        <aside className="venue-aside">
          <div className="info-card">
            <h3>
              <Clock3 size={16} /> Opening hours
            </h3>
            <ul>
              {groupHours(venue.hours).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            <small>Times are Philippine time.</small>
          </div>
          <div className="info-card">
            <h3>
              <CalendarClock size={16} /> Booking rules
            </h3>
            <ul>
              <li>{rules.requiresApproval ? 'The venue approves each request.' : 'Bookings are confirmed instantly.'}</li>
              <li>
                Book {durationLabel(rules.minBookingMinutes)} to {durationLabel(rules.maxBookingMinutes)}, up to {rules.maxAdvanceDays} days ahead.
              </li>
              <li>At least {durationLabel(rules.minNoticeMinutes)} notice.</li>
              <li>
                {rules.cancellationWindowHours
                  ? `Free cancellation until ${rules.cancellationWindowHours} hours before.`
                  : 'Free cancellation any time before the start.'}
              </li>
              <li>Payment is settled at the venue.</li>
            </ul>
          </div>
          {venue.amenities.length > 0 && (
            <div className="info-card">
              <h3>Amenities</h3>
              <div className="chip-row">
                {venue.amenities.map((item) => (
                  <span key={item} className="chip chip-static">
                    {item}
                  </span>
                ))}
              </div>
            </div>
          )}
          {venue.latitude !== null && venue.longitude !== null && (
            <LazyMap height={240} points={[{ id: venue.id, latitude: venue.latitude, longitude: venue.longitude, title: venue.name, subtitle: placeLine(venue.location) }]} />
          )}
          {venue.isDemo && <small className="form-hint">Demo venue: the map position is an approximate city centre.</small>}
        </aside>
      </div>

      {selection && summary && (
        <div className="booking-bar" role="region" aria-label="Your selection">
          <div>
            <strong>
              {selection.resource.name} · {relativeDayLabel(date, today)}
            </strong>
            <span>
              {formatTimeRange(summary.startAt, summary.endAt)} · {durationLabel(summary.minutes)} · {priceLabel(summary.price)}
            </span>
            {tooShort && <small>Minimum booking is {durationLabel(rules.minBookingMinutes)}. Tap a later slot to extend.</small>}
          </div>
          <button className="button button-lime" disabled={tooShort} onClick={() => requireAuth('Sign in to reserve this time.', () => setConfirming(true))}>
            Continue
          </button>
        </div>
      )}

      {confirming && selection && summary && (
        <ConfirmBooking
          venue={venue}
          selection={selection}
          summary={summary}
          dayLabel={relativeDayLabel(date, today)}
          preferredSport={sportId}
          onClose={() => setConfirming(false)}
          onBooked={(message) => {
            notify(message)
            navigate('/bookings')
          }}
          onConflict={(message) => {
            notify(message, 'error')
            setConfirming(false)
            setSelection(null)
            availability.reload()
          }}
        />
      )}
    </div>
  )
}

interface ConfirmProps {
  venue: FacilityDetail
  selection: Selection
  summary: ReturnType<typeof selectionSummary>
  dayLabel: string
  preferredSport: string
  onClose: () => void
  onBooked: (message: string) => void
  onConflict: (message: string) => void
}

function ConfirmBooking({ venue, selection, summary, dayLabel, preferredSport, onClose, onBooked, onConflict }: ConfirmProps) {
  const sports = venue.sports.filter((sport) => selection.resource.sportIds.includes(sport.id))
  const [sportId, setSportId] = useState(sports.some((sport) => sport.id === preferredSport) ? preferredSport : (sports[0]?.id ?? ''))
  const [partySize, setPartySize] = useState(Math.min(2, selection.resource.capacity))
  const [repeatWeeks, setRepeatWeeks] = useState(1)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const maxWeeks = Math.max(1, Math.min(8, Math.floor(venue.bookingRules.maxAdvanceDays / 7)))

  async function submit() {
    setBusy(true)
    setError('')
    try {
      const reservations = await api.book({
        resourceId: selection.resource.id,
        startAt: summary.startAt,
        endAt: summary.endAt,
        sportId: sportId || undefined,
        partySize,
        note: note.trim(),
        repeatWeeks,
      })
      const pending = reservations[0].status === 'pending'
      onBooked(pending ? 'Request sent. The venue will confirm it.' : reservations.length > 1 ? `Booked ${reservations.length} weekly sessions.` : 'You’re booked!')
    } catch (reason) {
      const failure = reason instanceof ApiError ? reason : new ApiError(0, 'Something went wrong. Please try again.')
      if (failure.status === 409) onConflict(failure.message)
      else setError(failure.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title="Confirm your reservation" onClose={onClose}>
      <div className="summary-box">
        <strong>{selection.resource.name}</strong>
        <span>{venue.name}</span>
        <span>
          {dayLabel} · {formatTimeRange(summary.startAt, summary.endAt)} ({durationLabel(summary.minutes)})
        </span>
        <b>
          {priceLabel(summary.price)}
          {repeatWeeks > 1 && ` × ${repeatWeeks} weeks`} · pay at the venue
        </b>
        {venue.isDemo && <small>Demo venue: this is a sample booking and no real court is reserved.</small>}
      </div>
      <div className="form">
        {sports.length > 1 && (
          <label className="field">
            <span>Sport</span>
            <select value={sportId} onChange={(event) => setSportId(event.target.value)}>
              {sports.map((sport) => (
                <option key={sport.id} value={sport.id}>
                  {sport.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="field">
          <span>How many people (up to {selection.resource.capacity})</span>
          <input
            type="number"
            min={1}
            max={selection.resource.capacity}
            value={partySize}
            onChange={(event) => setPartySize(Math.max(1, Math.min(selection.resource.capacity, Number(event.target.value) || 1)))}
          />
        </label>
        {maxWeeks > 1 && (
          <label className="field">
            <span>Repeat</span>
            <select value={repeatWeeks} onChange={(event) => setRepeatWeeks(Number(event.target.value))}>
              <option value={1}>Just this once</option>
              {Array.from({ length: maxWeeks - 1 }, (_, index) => index + 2).map((weeks) => (
                <option key={weeks} value={weeks}>
                  Weekly for {weeks} weeks
                </option>
              ))}
            </select>
            {repeatWeeks > 1 && <small>All {repeatWeeks} dates are booked together. If any one is taken, none are booked.</small>}
          </label>
        )}
        <label className="field">
          <span>Note for the venue (optional)</span>
          <input value={note} onChange={(event) => setNote(event.target.value)} maxLength={500} />
        </label>
        {venue.bookingRules.requiresApproval && <p className="form-hint">This venue reviews requests. Your time is held while they decide.</p>}
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button className="button button-primary button-block" onClick={submit} disabled={busy}>
          {busy ? 'Booking…' : venue.bookingRules.requiresApproval ? 'Send booking request' : 'Confirm booking'}
        </button>
      </div>
    </Modal>
  )
}
