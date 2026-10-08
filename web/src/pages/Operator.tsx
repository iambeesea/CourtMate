import { ArrowLeft, Building2, Plus, ShieldAlert, ShieldCheck } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { CityPicker } from '../components/CityPicker'
import { Modal } from '../components/Modal'
import { OperatorBookings, OperatorHours, OperatorOverview, OperatorSchedule, OperatorSpaces } from '../components/OperatorTabs'
import { SportIcon } from '../components/SportIcon'
import { DemoBadge, EmptyState, ErrorState, Loading } from '../components/StateViews'
import { ApiError, api } from '../lib/api'
import { placeLine, plural } from '../lib/format'
import type { OperatorFacility, Place } from '../lib/types'
import { useAsync } from '../lib/useAsync'
import { useAuth } from '../state/auth'
import { useCatalog } from '../state/catalog'
import { useToast } from '../state/toast'

const STATUS_COPY: Record<string, { label: string; tone: string; help: string }> = {
  pending: { label: 'Awaiting verification', tone: 'status-pending', help: 'Players cannot see or book this venue yet. Set up your spaces and hours while it is reviewed.' },
  verified: { label: 'Verified', tone: 'status-confirmed', help: 'Listed publicly and open for bookings.' },
  rejected: { label: 'Not verified', tone: 'status-cancelled', help: 'This venue was not verified and is not listed.' },
  suspended: { label: 'Suspended', tone: 'status-cancelled', help: 'This venue has been taken off the listings.' },
}

function SignInGate({ children }: { children: ReactNode }) {
  const { user, ready, openAuth } = useAuth()
  if (!ready) return <Loading />
  if (user) return <>{children}</>
  return (
    <div className="page">
      <EmptyState
        icon={<Building2 size={24} />}
        title="Venue dashboard"
        action={
          <button className="button button-primary" onClick={() => openAuth('Sign in to manage a venue.')}>
            Sign in
          </button>
        }
      >
        Sign in to register a venue, set its spaces and hours, and manage reservations.
      </EmptyState>
    </div>
  )
}

export function OperatorHome() {
  return (
    <SignInGate>
      <OperatorList />
    </SignInGate>
  )
}

function OperatorList() {
  const { user } = useAuth()
  const facilities = useAsync(() => api.operatorFacilities(), [user?.id])
  const [registering, setRegistering] = useState(false)

  return (
    <div className="page">
      <div className="page-title stats-title">
        <div>
          <span className="eyebrow">FOR VENUE OPERATORS</span>
          <h1>Venue dashboard</h1>
          <p>Register your facility, list what can be booked, and manage reservations.</p>
        </div>
        <button className="button button-primary" onClick={() => setRegistering(true)}>
          <Plus size={17} /> Register a venue
        </button>
      </div>

      {facilities.error && !facilities.data ? (
        <ErrorState error={facilities.error} onRetry={facilities.reload} />
      ) : !facilities.data ? (
        <Loading />
      ) : facilities.data.length === 0 ? (
        <EmptyState
          icon={<Building2 size={24} />}
          title="No venues yet"
          action={
            <button className="button button-primary" onClick={() => setRegistering(true)}>
              Register a venue
            </button>
          }
        >
          Courts, fields, lanes, tables, studios and pools can all be listed. A new venue is reviewed before players can see it.
        </EmptyState>
      ) : (
        <div className="card-grid">
          {facilities.data.map((facility) => {
            const status = STATUS_COPY[facility.verificationStatus]
            return (
              <Link key={facility.id} to={`/operator/${facility.id}`} className="card">
                <div className="card-top">
                  <span className={`status-badge ${status.tone}`}>{status.label}</span>
                  {facility.isDemo && <DemoBadge />}
                </div>
                <h3>{facility.name}</h3>
                <p className="meta-line">{placeLine(facility.location)}</p>
                <div className="card-foot">
                  <strong>{plural(facility.resourceCount, 'space')}</strong>
                  <span>{facility.pendingRequests ? `${plural(facility.pendingRequests, 'request')} waiting` : 'No requests waiting'}</span>
                </div>
              </Link>
            )
          })}
        </div>
      )}
      {registering && <RegisterFacility onClose={() => setRegistering(false)} />}
    </div>
  )
}

function RegisterFacility({ onClose }: { onClose: () => void }) {
  const { sports } = useCatalog()
  const { user } = useAuth()
  const navigate = useNavigate()
  const notify = useToast()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [addressLine, setAddressLine] = useState('')
  const [city, setCity] = useState<Place | null>(null)
  const [barangayCode, setBarangayCode] = useState('')
  const [sportIds, setSportIds] = useState<string[]>([])
  const [contactName, setContactName] = useState(user?.displayName ?? '')
  const [contactEmail, setContactEmail] = useState(user?.email ?? '')
  const [contactPhone, setContactPhone] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const barangays = useAsync(() => api.barangays(city?.code ?? ''), [city?.code], Boolean(city))
  const bookable = sports.filter((sport) => sport.bookingEligible)

  async function submit() {
    if (!city) return setError('Choose the city or municipality.')
    setBusy(true)
    setError('')
    try {
      const facility = await api.registerFacility({
        name: name.trim(),
        description: description.trim(),
        addressLine: addressLine.trim(),
        cityCode: city.code,
        barangayCode: barangayCode || null,
        amenities: [],
        sportIds,
        contactName: contactName.trim(),
        contactEmail: contactEmail.trim(),
        contactPhone: contactPhone.trim(),
      })
      notify('Venue registered. It is now waiting for verification.')
      navigate(`/operator/${facility.id}`)
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'Could not register the venue.')
      setBusy(false)
    }
  }

  return (
    <Modal title="Register a venue" onClose={onClose} wide>
      <div className="form">
        <label className="field">
          <span>Venue name</span>
          <input value={name} onChange={(event) => setName(event.target.value)} minLength={3} maxLength={160} />
        </label>
        <label className="field">
          <span>Description</span>
          <textarea rows={3} maxLength={2000} value={description} onChange={(event) => setDescription(event.target.value)} />
        </label>
        <label className="field">
          <span>Street address</span>
          <input value={addressLine} onChange={(event) => setAddressLine(event.target.value)} maxLength={255} />
        </label>
        <CityPicker
          value={city}
          onChange={(value) => {
            setCity(value)
            setBarangayCode('')
          }}
        />
        {city && (
          <label className="field">
            <span>Barangay (optional)</span>
            <select value={barangayCode} onChange={(event) => setBarangayCode(event.target.value)}>
              <option value="">Not specified</option>
              {barangays.data?.map((item) => (
                <option key={item.code} value={item.code}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <div className="field">
          <span>Sports played here</span>
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
                  <SportIcon sport={sport} size="sm" /> {sport.name}
                </button>
              )
            })}
          </div>
        </div>
        <fieldset className="private-fields">
          <legend>Contact for verification — never shown to players</legend>
          <label className="field">
            <span>Contact person</span>
            <input value={contactName} onChange={(event) => setContactName(event.target.value)} maxLength={120} autoComplete="name" />
          </label>
          <div className="field-pair">
            <label className="field">
              <span>Email</span>
              <input type="email" value={contactEmail} onChange={(event) => setContactEmail(event.target.value)} autoComplete="email" />
            </label>
            <label className="field">
              <span>Phone</span>
              <input type="tel" value={contactPhone} onChange={(event) => setContactPhone(event.target.value)} maxLength={40} autoComplete="tel" />
            </label>
          </div>
        </fieldset>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button className="button button-primary button-block" onClick={submit} disabled={busy || name.trim().length < 3 || sportIds.length === 0 || contactName.trim().length < 2}>
          {busy ? 'Registering…' : 'Register venue'}
        </button>
      </div>
    </Modal>
  )
}

const TABS = ['Overview', 'Bookings', 'Schedule', 'Spaces', 'Hours and rules', 'Details'] as const
type Tab = (typeof TABS)[number]

export function OperatorFacilityPage() {
  return (
    <SignInGate>
      <FacilityDashboard />
    </SignInGate>
  )
}

function FacilityDashboard() {
  const { id = '' } = useParams()
  const { user } = useAuth()
  const facility = useAsync(() => api.operatorFacility(id), [id, user?.id])
  const [tab, setTab] = useState<Tab>('Overview')

  if (facility.error && !facility.data) {
    return (
      <div className="page">
        <ErrorState error={facility.error} onRetry={facility.reload} />
      </div>
    )
  }
  if (!facility.data) return <Loading label="Loading venue…" />
  const data = facility.data
  const status = STATUS_COPY[data.verificationStatus]
  const update = (next: OperatorFacility) => facility.setData(next)

  return (
    <div className="page operator-page">
      <Link to="/operator" className="back-link">
        <ArrowLeft size={16} /> Venue dashboard
      </Link>
      <header className="venue-header">
        <div className="badge-line">
          <span className={`status-badge ${status.tone}`}>
            {data.verificationStatus === 'verified' ? <ShieldCheck size={12} /> : <ShieldAlert size={12} />} {status.label}
          </span>
          {data.isDemo && <DemoBadge label="Demo venue" />}
          {data.pendingRequests > 0 && <span className="status-badge status-pending">{plural(data.pendingRequests, 'request')} waiting</span>}
        </div>
        <h1>{data.name}</h1>
        <p className="meta-line">{[data.addressLine, placeLine(data.location), data.location.region.name].filter(Boolean).join(' · ')}</p>
        {data.verificationStatus !== 'verified' && (
          <p className="notice">
            {status.help} {data.verificationNotes && `Reviewer’s note: ${data.verificationNotes}`}
          </p>
        )}
      </header>

      <div className="filters operator-tabs" role="tablist" aria-label="Dashboard sections">
        {TABS.map((item) => (
          <button key={item} role="tab" aria-selected={tab === item} className={tab === item ? 'active' : ''} onClick={() => setTab(item)}>
            {item}
            {item === 'Bookings' && data.pendingRequests > 0 && <b>{data.pendingRequests}</b>}
          </button>
        ))}
      </div>

      {tab === 'Overview' && <OperatorOverview facility={data} onOpenBookings={() => setTab('Bookings')} />}
      {tab === 'Bookings' && <OperatorBookings facility={data} onChanged={facility.reload} />}
      {tab === 'Schedule' && <OperatorSchedule facility={data} />}
      {tab === 'Spaces' && <OperatorSpaces facility={data} onChanged={update} />}
      {tab === 'Hours and rules' && <OperatorHours facility={data} onChanged={update} />}
      {tab === 'Details' && <FacilityDetails facility={data} onChanged={update} />}
    </div>
  )
}

function FacilityDetails({ facility, onChanged }: { facility: OperatorFacility; onChanged: (facility: OperatorFacility) => void }) {
  const notify = useToast()
  const [name, setName] = useState(facility.name)
  const [description, setDescription] = useState(facility.description)
  const [addressLine, setAddressLine] = useState(facility.addressLine)
  const [amenities, setAmenities] = useState(facility.amenities.join(', '))
  const [latitude, setLatitude] = useState(facility.latitude?.toString() ?? '')
  const [longitude, setLongitude] = useState(facility.longitude?.toString() ?? '')
  const [contactName, setContactName] = useState(facility.contactName)
  const [contactEmail, setContactEmail] = useState(facility.contactEmail)
  const [contactPhone, setContactPhone] = useState(facility.contactPhone)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function save() {
    setBusy(true)
    setError('')
    try {
      onChanged(
        await api.updateFacility(facility.id, {
          name: name.trim(),
          description: description.trim(),
          addressLine: addressLine.trim(),
          amenities: amenities
            .split(',')
            .map((item) => item.trim())
            .filter(Boolean),
          latitude: latitude === '' ? null : Number(latitude),
          longitude: longitude === '' ? null : Number(longitude),
          contactName: contactName.trim(),
          contactEmail: contactEmail.trim(),
          contactPhone: contactPhone.trim(),
        }),
      )
      notify('Venue details saved.')
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'Could not save.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="form operator-form">
      <label className="field">
        <span>Venue name</span>
        <input value={name} onChange={(event) => setName(event.target.value)} maxLength={160} />
      </label>
      <label className="field">
        <span>Description</span>
        <textarea rows={4} maxLength={2000} value={description} onChange={(event) => setDescription(event.target.value)} />
      </label>
      <label className="field">
        <span>Street address</span>
        <input value={addressLine} onChange={(event) => setAddressLine(event.target.value)} maxLength={255} />
      </label>
      <label className="field">
        <span>Amenities, separated by commas</span>
        <input value={amenities} onChange={(event) => setAmenities(event.target.value)} placeholder="Parking, Showers, Equipment rental" />
      </label>
      <div className="field-pair">
        <label className="field">
          <span>Latitude</span>
          <input type="number" step="any" value={latitude} onChange={(event) => setLatitude(event.target.value)} />
        </label>
        <label className="field">
          <span>Longitude</span>
          <input type="number" step="any" value={longitude} onChange={(event) => setLongitude(event.target.value)} />
          <small>Coordinates put the venue on the map and in “near me” searches.</small>
        </label>
      </div>
      <fieldset className="private-fields">
        <legend>Private contact — visible only to you and CourtMate administrators</legend>
        <label className="field">
          <span>Contact person</span>
          <input value={contactName} onChange={(event) => setContactName(event.target.value)} maxLength={120} />
        </label>
        <div className="field-pair">
          <label className="field">
            <span>Email</span>
            <input type="email" value={contactEmail} onChange={(event) => setContactEmail(event.target.value)} />
          </label>
          <label className="field">
            <span>Phone</span>
            <input type="tel" value={contactPhone} onChange={(event) => setContactPhone(event.target.value)} maxLength={40} />
          </label>
        </div>
      </fieldset>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <button className="button button-primary" onClick={save} disabled={busy || name.trim().length < 3}>
        {busy ? 'Saving…' : 'Save details'}
      </button>
    </div>
  )
}
