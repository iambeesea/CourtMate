import { Ban, Check, Plus, X } from 'lucide-react'
import { useState } from 'react'
import { ApiError, api } from '../lib/api'
import {
  addDays,
  dateKey,
  durationLabel,
  formatMediumDate,
  formatTime,
  formatTimeRange,
  keyParts,
  manilaIso,
  minutesBetween,
  peso,
  plural,
  priceLabel,
  WEEKDAY_NAMES,
} from '../lib/format'
import type { OperatorFacility, Reservation, ResourceDraft, ResourceInfo } from '../lib/types'
import { useAsync } from '../lib/useAsync'
import { useCatalog } from '../state/catalog'
import { useToast } from '../state/toast'
import { Modal } from './Modal'
import { EmptyState, ErrorState, Loading } from './StateViews'

interface TabProps {
  facility: OperatorFacility
}

interface EditableTabProps extends TabProps {
  onChanged: (facility: OperatorFacility) => void
}

function describe(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback
}

function minuteToClock(minute: number): string {
  return `${String(Math.floor(minute / 60) % 24).padStart(2, '0')}:${String(minute % 60).padStart(2, '0')}`
}

function clockToMinute(clock: string, closing = false): number {
  const [hours, minutes] = clock.split(':').map(Number)
  const total = hours * 60 + minutes
  // A closing time of 00:00 means midnight at the end of the day.
  return closing && total === 0 ? 1440 : total
}

// --- overview -----------------------------------------------------------------

export function OperatorOverview({ facility, onOpenBookings }: TabProps & { onOpenBookings: () => void }) {
  const report = useAsync(() => api.occupancy(facility.id), [facility.id])
  if (report.error && !report.data) return <ErrorState error={report.error} onRetry={report.reload} />
  if (!report.data) return <Loading />
  const data = report.data

  return (
    <div className="operator-section">
      <p className="form-hint">
        Next seven days, {formatMediumDate(`${data.dateFrom}T04:00:00Z`)} to {formatMediumDate(`${data.dateTo}T04:00:00Z`)}.
      </p>
      <div className="stat-grid">
        <div className="stat-card">
          <strong>{data.occupancyPercent}%</strong>
          <span>Occupancy</span>
          <small>
            {durationLabel(data.bookedMinutes)} booked of {durationLabel(data.openMinutes)} open
          </small>
        </div>
        <button className="stat-card stat-card-link" onClick={onOpenBookings}>
          <strong>{data.pendingBookings}</strong>
          <span>Requests waiting</span>
          <small>Open bookings</small>
        </button>
        <div className="stat-card">
          <strong>{data.confirmedBookings}</strong>
          <span>Confirmed bookings</span>
          <small>{plural(data.cancelledBookings, 'cancellation')}</small>
        </div>
        <div className="stat-card">
          <strong>{peso(data.bookedValueCentavos)}</strong>
          <span>Booked value</span>
          <small>At listed rates. Not a record of money received.</small>
        </div>
      </div>

      {data.resources.length === 0 ? (
        <p className="notice">Add your first bookable space under “Spaces” to start taking reservations.</p>
      ) : (
        <div className="occupancy-list">
          {data.resources.map((item) => (
            <div key={item.resourceId} className="occupancy-row">
              <strong>{item.name}</strong>
              <div className="occupancy-bar" role="img" aria-label={`${item.occupancyPercent}% booked`}>
                <span style={{ width: `${Math.min(100, item.occupancyPercent)}%` }} />
                <i style={{ width: `${item.openMinutes ? Math.min(100, (item.blockedMinutes / item.openMinutes) * 100) : 0}%` }} />
              </div>
              <small>
                {item.occupancyPercent}% booked{item.blockedMinutes > 0 && ` · ${durationLabel(item.blockedMinutes)} blocked`}
              </small>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// --- bookings -----------------------------------------------------------------

export function OperatorBookings({ facility, onChanged }: TabProps & { onChanged: () => void }) {
  const notify = useToast()
  const [scope, setScope] = useState<'pending' | 'upcoming' | 'past'>(facility.pendingRequests ? 'pending' : 'upcoming')
  const reservations = useAsync(() => api.operatorReservations(facility.id, scope), [facility.id, scope])
  const [acting, setActing] = useState<{ reservation: Reservation; action: 'reject' | 'cancel' } | null>(null)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)

  async function decide(reservation: Reservation, action: 'confirm' | 'reject' | 'cancel', why = '') {
    setBusy(true)
    try {
      await api.decideReservation(reservation.id, action, why)
      notify(action === 'confirm' ? 'Booking confirmed. The customer has been told.' : action === 'reject' ? 'Request declined.' : 'Booking cancelled.')
      setActing(null)
      setReason('')
      reservations.reload()
      onChanged()
    } catch (error) {
      notify(describe(error, 'That didn’t work. Please try again.'), 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="operator-section">
      <div className="segmented" role="tablist">
        {(['pending', 'upcoming', 'past'] as const).map((value) => (
          <button key={value} role="tab" aria-selected={scope === value} className={scope === value ? 'active' : ''} onClick={() => setScope(value)}>
            {value === 'pending' ? 'Requests' : value === 'upcoming' ? 'Upcoming' : 'History'}
          </button>
        ))}
      </div>

      {reservations.error && !reservations.data ? (
        <ErrorState error={reservations.error} onRetry={reservations.reload} />
      ) : !reservations.data ? (
        <Loading />
      ) : reservations.data.length === 0 ? (
        <p className="notice">{scope === 'pending' ? 'No requests are waiting for a decision.' : scope === 'upcoming' ? 'Nothing is booked yet.' : 'No past reservations.'}</p>
      ) : (
        <div className="upcoming-list">
          {reservations.data.map((item) => {
            const day = keyParts(dateKey(item.startAt))
            return (
              <article className="booking-card" key={item.id}>
                <div className="large-date">
                  <span>{day.weekday}</span>
                  <strong>{day.day}</strong>
                  <small>{day.month}</small>
                </div>
                <div className="booking-main">
                  <div className="badge-line">
                    <span className={`status-badge status-${item.status}`}>{item.status}</span>
                    {item.sport && <span className="sport-badge">{item.sport.name}</span>}
                    {item.lateCancellation && <span className="status-badge status-cancelled">Late cancellation</span>}
                  </div>
                  <h3>
                    {item.resource.name} · {item.organizer.displayName}
                  </h3>
                  <p className="meta-line">
                    {formatTimeRange(item.startAt, item.endAt)} · {durationLabel(minutesBetween(item.startAt, item.endAt))} · {plural(item.partySize, 'person', 'people')}
                  </p>
                  {item.note && <p className="meta-line">“{item.note}”</p>}
                  {item.cancelReason && <p className="meta-line">Reason: {item.cancelReason}</p>}
                </div>
                <div className="booking-side">
                  <strong>{priceLabel(item.priceCentavos)}</strong>
                  {item.status === 'pending' && (
                    <div className="button-row">
                      <button className="button button-primary button-small" disabled={busy} onClick={() => decide(item, 'confirm')}>
                        <Check size={15} /> Accept
                      </button>
                      <button className="button button-ghost button-small" disabled={busy} onClick={() => setActing({ reservation: item, action: 'reject' })}>
                        <X size={15} /> Decline
                      </button>
                    </div>
                  )}
                  {item.status === 'confirmed' && item.canCancel && (
                    <button className="button button-ghost button-small" disabled={busy} onClick={() => setActing({ reservation: item, action: 'cancel' })}>
                      Cancel
                    </button>
                  )}
                </div>
              </article>
            )
          })}
        </div>
      )}

      {acting && (
        <Modal title={acting.action === 'reject' ? 'Decline this request?' : 'Cancel this booking?'} onClose={() => setActing(null)} variant="dialog">
          <p>
            <strong>{acting.reservation.resource.name}</strong> for {acting.reservation.organizer.displayName}, {formatMediumDate(acting.reservation.startAt)} at{' '}
            {formatTime(acting.reservation.startAt)}. The customer will be notified and the time becomes available again.
          </p>
          <label className="field">
            <span>Reason shown to the customer</span>
            <input value={reason} onChange={(event) => setReason(event.target.value)} maxLength={300} />
          </label>
          <div className="button-row">
            <button className="button button-danger" disabled={busy} onClick={() => decide(acting.reservation, acting.action, reason.trim())}>
              {acting.action === 'reject' ? 'Decline request' : 'Cancel booking'}
            </button>
            <button className="button button-ghost" onClick={() => setActing(null)}>
              Keep it
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}

// --- schedule and blocks ------------------------------------------------------

export function OperatorSchedule({ facility }: TabProps) {
  const notify = useToast()
  const today = dateKey()
  const [date, setDate] = useState(today)
  const schedule = useAsync(() => api.operatorSchedule(facility.id, date), [facility.id, date])
  const blocks = useAsync(() => api.operatorReservations(facility.id, 'blocks'), [facility.id])
  const [resourceId, setResourceId] = useState(facility.resources[0]?.id ?? '')
  const [from, setFrom] = useState('08:00')
  const [to, setTo] = useState('10:00')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const days = Array.from({ length: 14 }, (_, index) => addDays(today, index))

  async function block() {
    setBusy(true)
    try {
      await api.blockTime(resourceId, manilaIso(date, from), manilaIso(date, to), reason.trim())
      notify('Time blocked.')
      setReason('')
      schedule.reload()
      blocks.reload()
    } catch (error) {
      notify(describe(error, 'Could not block that time.'), 'error')
    } finally {
      setBusy(false)
    }
  }

  async function unblock(id: string) {
    try {
      await api.removeBlock(id)
      notify('Block removed.')
      schedule.reload()
      blocks.reload()
    } catch (error) {
      notify(describe(error, 'Could not remove the block.'), 'error')
    }
  }

  if (facility.resources.length === 0) return <p className="notice">Add a bookable space first, then its schedule appears here.</p>

  return (
    <div className="operator-section">
      <div className="day-strip" role="tablist" aria-label="Date">
        {days.map((key) => {
          const parts = keyParts(key)
          return (
            <button key={key} role="tab" aria-selected={date === key} className={`day-chip ${date === key ? 'active' : ''}`} onClick={() => setDate(key)}>
              <span>{key === today ? 'TODAY' : parts.weekday}</span>
              <strong>{parts.day}</strong>
              <small>{parts.month}</small>
            </button>
          )
        })}
      </div>

      {schedule.error && !schedule.data ? (
        <ErrorState error={schedule.error} onRetry={schedule.reload} />
      ) : !schedule.data ? (
        <Loading />
      ) : !schedule.data.isOpen ? (
        <p className="notice">Closed on this day. Change opening hours under “Hours and rules”.</p>
      ) : (
        <div className="resource-list">
          {schedule.data.resources.map(({ resource, slots }) => (
            <article key={resource.id} className="resource-row">
              <div className="resource-head">
                <div>
                  <h3>
                    {resource.name} {!resource.isActive && <span className="status-badge">Off sale</span>}
                  </h3>
                  <p>
                    {slots.filter((slot) => slot.status === 'booked').length} booked · {slots.filter((slot) => slot.status === 'blocked').length} blocked ·{' '}
                    {slots.filter((slot) => slot.status === 'available').length} open
                  </p>
                </div>
              </div>
              <div className="slot-row">
                {slots.map((slot) => (
                  <span key={slot.startAt} className={`slot slot-static slot-${slot.status}`} title={slot.status}>
                    {formatTime(slot.startAt)}
                  </span>
                ))}
              </div>
            </article>
          ))}
          <p className="slot-legend">
            <span className="slot-key slot-available" /> Open <span className="slot-key slot-booked" /> Booked <span className="slot-key slot-blocked" /> Blocked
          </p>
        </div>
      )}

      <fieldset className="block-form">
        <legend>Block time on {formatMediumDate(`${date}T04:00:00Z`)}</legend>
        <div className="field-pair">
          <label className="field">
            <span>Space</span>
            <select value={resourceId} onChange={(event) => setResourceId(event.target.value)}>
              {facility.resources.map((resource) => (
                <option key={resource.id} value={resource.id}>
                  {resource.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>From</span>
            <input type="time" step={900} value={from} onChange={(event) => setFrom(event.target.value)} />
          </label>
          <label className="field">
            <span>To</span>
            <input type="time" step={900} value={to} onChange={(event) => setTo(event.target.value)} />
          </label>
          <label className="field">
            <span>Reason (only you see this)</span>
            <input value={reason} onChange={(event) => setReason(event.target.value)} maxLength={300} placeholder="Maintenance, private event…" />
          </label>
        </div>
        <button className="button button-primary" onClick={block} disabled={busy || !resourceId}>
          <Ban size={16} /> Block this time
        </button>
        <p className="form-hint">Blocking fails if a booking is already in that period, so nothing is double-booked.</p>
      </fieldset>

      {(blocks.data?.length ?? 0) > 0 && (
        <div className="history-list">
          {blocks.data?.map((item) => (
            <div key={item.id} className="history-row">
              <Ban size={18} />
              <div>
                <strong>{item.resource.name}</strong>
                <small>
                  {formatMediumDate(item.startAt)}, {formatTimeRange(item.startAt, item.endAt)} {item.note && `· ${item.note}`}
                </small>
              </div>
              <button className="button button-ghost button-small" onClick={() => unblock(item.id)}>
                Remove
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// --- spaces -------------------------------------------------------------------

export function OperatorSpaces({ facility, onChanged }: EditableTabProps) {
  const notify = useToast()
  const [editing, setEditing] = useState<ResourceInfo | 'new' | null>(null)

  async function toggle(resource: ResourceInfo) {
    try {
      onChanged(await api.updateResource(resource.id, { isActive: !resource.isActive }))
      notify(resource.isActive ? `${resource.name} is off sale.` : `${resource.name} is bookable again.`)
    } catch (error) {
      notify(describe(error, 'Could not update that space.'), 'error')
    }
  }

  return (
    <div className="operator-section">
      <div className="toolbar">
        <p className="form-hint">Courts, fields, lanes, tables, studios, pools: anything players can reserve.</p>
        <button className="button button-primary button-small" onClick={() => setEditing('new')}>
          <Plus size={16} /> Add a space
        </button>
      </div>
      {facility.resources.length === 0 ? (
        <EmptyState icon={<Plus size={24} />} title="No bookable spaces yet">
          Add each court, field, lane or room with its price and booking length.
        </EmptyState>
      ) : (
        <div className="resource-list">
          {facility.resources.map((resource) => (
            <article key={resource.id} className={`resource-row ${resource.parentId ? 'is-section' : ''}`}>
              <div className="resource-head">
                <div>
                  <h3>
                    {resource.name} {!resource.isActive && <span className="status-badge">Off sale</span>}
                  </h3>
                  <p>
                    {resource.resourceType.name} · up to {resource.capacity} · {durationLabel(resource.slotMinutes)} slots
                    {resource.parentId && ` · section of ${facility.resources.find((item) => item.id === resource.parentId)?.name ?? 'another space'}`}
                    {resource.childIds.length > 0 && ` · booking it takes all ${resource.childIds.length} sections`}
                  </p>
                </div>
                <strong>{resource.hourlyRateCentavos ? `${peso(resource.hourlyRateCentavos)}/hr` : 'Free'}</strong>
              </div>
              <div className="button-row">
                <button className="button button-ghost button-small" onClick={() => setEditing(resource)}>
                  Edit
                </button>
                <button className="button button-ghost button-small" onClick={() => toggle(resource)}>
                  {resource.isActive ? 'Take off sale' : 'Put back on sale'}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
      {editing && (
        <SpaceDialog
          facility={facility}
          resource={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={(next) => {
            onChanged(next)
            setEditing(null)
            notify('Saved.')
          }}
        />
      )}
    </div>
  )
}

function SpaceDialog({ facility, resource, onClose, onSaved }: { facility: OperatorFacility; resource: ResourceInfo | null; onClose: () => void; onSaved: (facility: OperatorFacility) => void }) {
  const { sports } = useCatalog()
  const types = useAsync(() => api.resourceTypes(), [])
  const [name, setName] = useState(resource?.name ?? '')
  const [typeId, setTypeId] = useState(resource?.resourceType.id ?? 'court')
  const [sportIds, setSportIds] = useState<string[]>(resource?.sportIds ?? facility.sports.slice(0, 1).map((sport) => sport.id))
  const [capacity, setCapacity] = useState(resource?.capacity ?? 4)
  const [slotMinutes, setSlotMinutes] = useState(resource?.slotMinutes ?? 60)
  const [rate, setRate] = useState((resource?.hourlyRateCentavos ?? 0) / 100)
  const [parentId, setParentId] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const bookable = sports.filter((sport) => sport.bookingEligible)
  const parents = facility.resources.filter((item) => !item.parentId)

  async function save() {
    setBusy(true)
    setError('')
    const draft: ResourceDraft = {
      name: name.trim(),
      resourceTypeId: typeId,
      sportIds,
      description: resource?.description ?? '',
      capacity,
      slotMinutes,
      hourlyRateCentavos: Math.round(rate * 100),
    }
    try {
      if (resource) onSaved(await api.updateResource(resource.id, { name: draft.name, sportIds, capacity, slotMinutes, hourlyRateCentavos: draft.hourlyRateCentavos }))
      else onSaved(await api.addResource(facility.id, { ...draft, parentId: parentId || null }))
    } catch (reason) {
      setError(describe(reason, 'Could not save.'))
      setBusy(false)
    }
  }

  return (
    <Modal title={resource ? `Edit ${resource.name}` : 'Add a bookable space'} onClose={onClose} wide>
      <div className="form">
        <label className="field">
          <span>Name</span>
          <input value={name} onChange={(event) => setName(event.target.value)} maxLength={120} placeholder="Court 1, Lane 3, Studio A…" />
        </label>
        {!resource && (
          <div className="field-pair">
            <label className="field">
              <span>Type</span>
              <select value={typeId} onChange={(event) => setTypeId(event.target.value)}>
                {types.data?.map((type) => (
                  <option key={type.id} value={type.id}>
                    {type.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Section of (optional)</span>
              <select value={parentId} onChange={(event) => setParentId(event.target.value)}>
                <option value="">A space on its own</option>
                {parents.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
              <small>Use this for half courts or pool lanes. Booking the whole space takes every section.</small>
            </label>
          </div>
        )}
        <div className="field">
          <span>Sports</span>
          <div className="chip-row">
            {bookable.map((sport) => {
              const on = sportIds.includes(sport.id)
              return (
                <button
                  type="button"
                  key={sport.id}
                  className={`chip ${on ? 'active' : ''}`}
                  aria-pressed={on}
                  onClick={() => setSportIds((current) => (on ? current.filter((id) => id !== sport.id) : [...current, sport.id]))}
                >
                  {sport.name}
                </button>
              )
            })}
          </div>
        </div>
        <div className="field-pair">
          <label className="field">
            <span>Holds up to</span>
            <input type="number" min={1} max={5000} value={capacity} onChange={(event) => setCapacity(Math.max(1, Number(event.target.value) || 1))} />
          </label>
          <label className="field">
            <span>Booking length</span>
            <select value={slotMinutes} onChange={(event) => setSlotMinutes(Number(event.target.value))}>
              {[15, 30, 45, 60, 90, 120, 180, 240].map((minutes) => (
                <option key={minutes} value={minutes}>
                  {durationLabel(minutes)}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Price per hour (₱)</span>
            <input type="number" min={0} step={10} value={rate} onChange={(event) => setRate(Math.max(0, Number(event.target.value) || 0))} />
          </label>
        </div>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button className="button button-primary button-block" onClick={save} disabled={busy || !name.trim() || sportIds.length === 0}>
          {busy ? 'Saving…' : 'Save space'}
        </button>
      </div>
    </Modal>
  )
}

// --- hours and rules ----------------------------------------------------------

export function OperatorHours({ facility, onChanged }: EditableTabProps) {
  const notify = useToast()
  const [days, setDays] = useState(() =>
    WEEKDAY_NAMES.map((_, weekday) => {
      const current = facility.hours.find((item) => item.weekday === weekday)
      return { open: Boolean(current), from: minuteToClock(current?.openMinute ?? 360), to: minuteToClock(current?.closeMinute ?? 1320) }
    }),
  )
  const [rules, setRules] = useState(facility.bookingRules)
  const [busy, setBusy] = useState(false)

  function setDay(weekday: number, changes: Partial<(typeof days)[number]>) {
    setDays((current) => current.map((day, index) => (index === weekday ? { ...day, ...changes } : day)))
  }

  async function saveHours() {
    setBusy(true)
    try {
      const hours = days.flatMap((day, weekday) => (day.open ? [{ weekday, openMinute: clockToMinute(day.from), closeMinute: clockToMinute(day.to, true) }] : []))
      onChanged(await api.setHours(facility.id, hours))
      notify('Opening hours saved.')
    } catch (error) {
      notify(describe(error, 'Could not save the hours.'), 'error')
    } finally {
      setBusy(false)
    }
  }

  async function saveRules() {
    setBusy(true)
    try {
      onChanged(await api.updateFacility(facility.id, rules))
      notify('Booking rules saved.')
    } catch (error) {
      notify(describe(error, 'Could not save the rules.'), 'error')
    } finally {
      setBusy(false)
    }
  }

  const number = (key: keyof typeof rules, minimum: number) => (
    <input type="number" min={minimum} value={Number(rules[key])} onChange={(event) => setRules((current) => ({ ...current, [key]: Math.max(minimum, Number(event.target.value) || minimum) }))} />
  )

  return (
    <div className="operator-section">
      <fieldset className="block-form">
        <legend>Opening hours (Philippine time)</legend>
        {days.map((day, weekday) => (
          <div key={weekday} className="hours-row">
            <label className="check">
              <input type="checkbox" checked={day.open} onChange={(event) => setDay(weekday, { open: event.target.checked })} /> {WEEKDAY_NAMES[weekday]}
            </label>
            {day.open ? (
              <>
                <input type="time" step={900} value={day.from} onChange={(event) => setDay(weekday, { from: event.target.value })} aria-label={`${WEEKDAY_NAMES[weekday]} opens`} />
                <span>to</span>
                <input type="time" step={900} value={day.to === '24:00' ? '00:00' : day.to} onChange={(event) => setDay(weekday, { to: event.target.value })} aria-label={`${WEEKDAY_NAMES[weekday]} closes`} />
              </>
            ) : (
              <small>Closed</small>
            )}
          </div>
        ))}
        <button className="button button-primary" onClick={saveHours} disabled={busy}>
          Save hours
        </button>
        <p className="form-hint">Times are on quarter hours. A closing time of 12:00 AM means midnight.</p>
      </fieldset>

      <fieldset className="block-form">
        <legend>Booking rules</legend>
        <label className="check">
          <input type="checkbox" checked={rules.requiresApproval} onChange={(event) => setRules((current) => ({ ...current, requiresApproval: event.target.checked }))} /> I approve each booking request
        </label>
        <div className="field-pair">
          <label className="field">
            <span>Minimum notice (minutes)</span>
            {number('minNoticeMinutes', 0)}
          </label>
          <label className="field">
            <span>Bookable up to (days ahead)</span>
            {number('maxAdvanceDays', 1)}
          </label>
          <label className="field">
            <span>Free cancellation until (hours before)</span>
            {number('cancellationWindowHours', 0)}
          </label>
          <label className="field">
            <span>Shortest booking (minutes)</span>
            {number('minBookingMinutes', 15)}
          </label>
          <label className="field">
            <span>Longest booking (minutes)</span>
            {number('maxBookingMinutes', 15)}
          </label>
        </div>
        <button className="button button-primary" onClick={saveRules} disabled={busy}>
          Save rules
        </button>
        <p className="form-hint">Payment is collected at the venue. Changes apply to new bookings; existing ones keep the cancellation terms they were made under.</p>
      </fieldset>
    </div>
  )
}
