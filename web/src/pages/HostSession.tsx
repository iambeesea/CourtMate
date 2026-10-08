import { ArrowLeft } from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { CityPicker } from '../components/CityPicker'
import { SportIcon } from '../components/SportIcon'
import { EmptyState, Loading } from '../components/StateViews'
import { ApiError, api } from '../lib/api'
import { addDays, dateKey, manilaIso, peso } from '../lib/format'
import type { Place, QueueMode, SessionDraft, SessionKind, Sport } from '../lib/types'
import { useAsync } from '../lib/useAsync'
import { useAuth } from '../state/auth'
import { useCatalog } from '../state/catalog'
import { useToast } from '../state/toast'

const KIND_LABELS: Record<SessionKind, string> = {
  open_play: 'Open play',
  pickup_game: 'Pickup game',
  class: 'Class',
  sparring: 'Sparring',
  group_activity: 'Group activity',
  tee_time: 'Tee time',
  challenge: 'Challenge match',
  tournament: 'Tournament',
  event: 'Event',
}

const QUEUE_LABELS: Record<QueueMode, string> = {
  none: 'No queue',
  rotation: 'Rotation (everyone to the back after each game)',
  winner_stays: 'Winner stays on court',
}

function kindLabel(sport: Sport, kind: SessionKind): string {
  return sport.matchFormat.kindLabels[kind] ?? KIND_LABELS[kind]
}

/** Sensible starting numbers for a sport, taken from its configuration. */
function defaultsFor(sport: Sport) {
  const format = sport.playerConfig.teamFormats[0]
  const perMatch = sport.matchFormat.type === 'two_sided' ? format.playersPerSide * 2 : 1
  return {
    kind: sport.matchFormat.sessionKinds[0],
    teamFormat: sport.matchFormat.type === 'two_sided' ? format.id : '',
    capacity: sport.matchFormat.type === 'two_sided' ? Math.max(perMatch * 2, 8) : 20,
    queueMode: (sport.queueEligible ? sport.matchFormat.queueModes[0] : 'none') as QueueMode,
    skillLevel: sport.matchFormat.skillLevels[0],
  }
}

export function HostSession() {
  const { user, ready, openAuth } = useAuth()
  const { sports, loading, sport: findSport } = useCatalog()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const notify = useToast()

  const initialSport = params.get('sport') ?? user?.sports.find((item) => item.isPrimary)?.sportId ?? ''
  const [sportId, setSportId] = useState(initialSport)
  const sport = findSport(sportId)
  const [form, setForm] = useState(() => ({
    title: '',
    description: '',
    kind: 'open_play' as SessionKind,
    date: addDays(dateKey(), 1),
    time: '18:00',
    minutes: 120,
    capacity: 12,
    minPlayers: 1,
    teamFormat: '',
    skillLevel: 'All levels',
    fee: 0,
    joinPolicy: 'open' as 'open' | 'approval',
    queueMode: 'none' as QueueMode,
    courtsInPlay: 1,
    hostPlays: true,
    repeatWeeks: 1,
    place: 'venue' as 'venue' | 'custom',
    facilityId: '',
    resourceId: '',
    venueName: '',
    meetupNote: '',
    routeName: '',
    routeKm: '',
  }))
  const [city, setCity] = useState<Place | null>(user?.city ?? null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const venues = useAsync(() => api.facilities({ sportId, limit: 100 }), [sportId], Boolean(sport?.bookingEligible))
  const venue = useAsync(() => api.facility(form.facilityId), [form.facilityId], Boolean(form.facilityId))
  const bookable = useMemo(() => (venue.data?.resources ?? []).filter((item) => item.sportIds.includes(sportId)), [venue.data, sportId])
  const usesVenue = Boolean(sport?.bookingEligible) && form.place === 'venue'
  // The form state can lag behind the chosen sport (for example when arriving with ?sport=golf),
  // so every sport-dependent value is checked against that sport's own options before use.
  const fallback = sport ? defaultsFor(sport) : null
  const kind = sport && sport.matchFormat.sessionKinds.includes(form.kind) ? form.kind : (fallback?.kind ?? form.kind)
  const teamFormat = sport && sport.playerConfig.teamFormats.some((item) => item.id === form.teamFormat) && sport.matchFormat.type === 'two_sided' ? form.teamFormat : (fallback?.teamFormat ?? '')
  const skillLevel = sport && sport.matchFormat.skillLevels.includes(form.skillLevel) ? form.skillLevel : (fallback?.skillLevel ?? form.skillLevel)
  const queueMode: QueueMode = sport?.queueEligible && (form.queueMode === 'none' || sport.matchFormat.queueModes.includes(form.queueMode)) ? form.queueMode : 'none'

  function set<Key extends keyof typeof form>(key: Key, value: (typeof form)[Key]) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  function chooseSport(id: string) {
    const next = findSport(id)
    setSportId(id)
    if (!next) return
    setForm((current) => ({
      ...current,
      ...defaultsFor(next),
      place: next.bookingEligible ? 'venue' : 'custom',
      facilityId: '',
      resourceId: '',
      courtsInPlay: 1,
    }))
  }

  if (!ready || loading) return <Loading />
  if (!user) {
    return (
      <div className="page">
        <EmptyState
          icon={<ArrowLeft size={24} />}
          title="Sign in to host"
          action={
            <button className="button button-primary" onClick={() => openAuth('Sign in to host a session.')}>
              Sign in
            </button>
          }
        >
          Hosting is free. You set the sport, place, time and how many can join.
        </EmptyState>
      </div>
    )
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!sport) return
    setError('')
    if (usesVenue && !form.facilityId) return setError('Choose a venue, or switch to “Somewhere else”.')
    if (!usesVenue && (!city || !form.venueName.trim())) return setError('Say which city and where to meet.')

    const startAt = manilaIso(form.date, form.time)
    const draft: SessionDraft = {
      title: form.title.trim(),
      description: form.description.trim(),
      sportId: sport.id,
      kind,
      startAt,
      endAt: new Date(new Date(startAt).getTime() + form.minutes * 60000).toISOString(),
      capacity: form.capacity,
      minPlayers: Math.min(form.minPlayers, form.capacity),
      skillLevel,
      teamFormat,
      genderEligibility: 'open',
      feeCentavos: Math.round(form.fee * 100),
      joinPolicy: form.joinPolicy,
      queueMode,
      courtsInPlay: queueMode === 'none' ? 1 : form.courtsInPlay,
      hostPlays: form.hostPlays,
      meetupNote: form.meetupNote.trim(),
      repeatWeeks: form.repeatWeeks,
    }
    if (usesVenue) {
      draft.facilityId = form.facilityId
      if (form.resourceId) draft.resourceId = form.resourceId
    } else {
      draft.cityCode = city?.code
      draft.venueName = form.venueName.trim()
      if (sport.matchFormat.usesRoutes) {
        draft.routeName = form.routeName.trim()
        if (form.routeKm) draft.routeDistanceKm = Number(form.routeKm)
      }
    }

    setBusy(true)
    try {
      const created = await api.createSession(draft)
      notify(created.length > 1 ? `${created.length} weekly sessions are live.` : 'Your session is live.')
      navigate(`/sessions/${created[0].id}`)
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'Could not create the session. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  const reserving = bookable.find((item) => item.id === form.resourceId)

  return (
    <div className="page host-page">
      <Link to="/play" className="back-link">
        <ArrowLeft size={16} /> Play
      </Link>
      <div className="page-title">
        <span className="eyebrow">HOST</span>
        <h1>Host a session</h1>
        <p>Pick a sport first. The form only asks what that sport needs.</p>
      </div>

      <form className="form host-form" onSubmit={submit}>
        <fieldset>
          <legend>Sport</legend>
          <div className="chip-row">
            {sports.map((item) => (
              <button type="button" key={item.id} className={`chip ${item.id === sportId ? 'active' : ''}`} aria-pressed={item.id === sportId} onClick={() => chooseSport(item.id)}>
                <SportIcon sport={item} size="sm" /> {item.name}
              </button>
            ))}
          </div>
        </fieldset>

        {sport && (
          <>
            <fieldset>
              <legend>What</legend>
              <label className="field">
                <span>Title</span>
                <input value={form.title} onChange={(event) => set('title', event.target.value)} required minLength={3} maxLength={120} placeholder={`e.g. Saturday ${sport.name.toLowerCase()} ${kindLabel(sport, kind).toLowerCase()}`} />
              </label>
              <div className="field-pair">
                {sport.matchFormat.sessionKinds.length > 1 && (
                  <label className="field">
                    <span>Type</span>
                    <select value={kind} onChange={(event) => set('kind', event.target.value as SessionKind)}>
                      {sport.matchFormat.sessionKinds.map((kind) => (
                        <option key={kind} value={kind}>
                          {kindLabel(sport, kind)}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                {sport.matchFormat.type === 'two_sided' && sport.playerConfig.teamFormats.length > 1 && (
                  <label className="field">
                    <span>Format</span>
                    <select value={teamFormat} onChange={(event) => set('teamFormat', event.target.value)}>
                      {sport.playerConfig.teamFormats.map((format) => (
                        <option key={format.id} value={format.id}>
                          {format.label}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                <label className="field">
                  <span>Skill level</span>
                  <select value={skillLevel} onChange={(event) => set('skillLevel', event.target.value)}>
                    {sport.matchFormat.skillLevels.map((level) => (
                      <option key={level}>{level}</option>
                    ))}
                  </select>
                </label>
              </div>
              <label className="field">
                <span>Details (optional)</span>
                <textarea rows={3} maxLength={2000} value={form.description} onChange={(event) => set('description', event.target.value)} placeholder="What to bring, parking, house rules…" />
              </label>
            </fieldset>

            <fieldset>
              <legend>When (Philippine time)</legend>
              <div className="field-pair">
                <label className="field">
                  <span>Date</span>
                  <input type="date" value={form.date} min={dateKey()} onChange={(event) => set('date', event.target.value)} required />
                </label>
                <label className="field">
                  <span>Start</span>
                  <input type="time" step={900} value={form.time} onChange={(event) => set('time', event.target.value)} required />
                </label>
                <label className="field">
                  <span>Length</span>
                  <select value={form.minutes} onChange={(event) => set('minutes', Number(event.target.value))}>
                    {[30, 60, 90, 120, 150, 180, 240, 300, 360].map((minutes) => (
                      <option key={minutes} value={minutes}>
                        {minutes < 60 ? `${minutes} min` : `${minutes / 60} hr`}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span>Repeat</span>
                  <select value={form.repeatWeeks} onChange={(event) => set('repeatWeeks', Number(event.target.value))}>
                    <option value={1}>Just once</option>
                    {[2, 3, 4, 6, 8].map((weeks) => (
                      <option key={weeks} value={weeks}>
                        Weekly for {weeks} weeks
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </fieldset>

            <fieldset>
              <legend>Where</legend>
              {sport.bookingEligible ? (
                <div className="segmented" role="tablist">
                  <button type="button" role="tab" aria-selected={form.place === 'venue'} className={form.place === 'venue' ? 'active' : ''} onClick={() => set('place', 'venue')}>
                    A listed venue
                  </button>
                  <button type="button" role="tab" aria-selected={form.place === 'custom'} className={form.place === 'custom' ? 'active' : ''} onClick={() => set('place', 'custom')}>
                    Somewhere else
                  </button>
                </div>
              ) : (
                <p className="form-hint">{sport.name} sessions meet at a route or public spot, so there is no venue to book.</p>
              )}

              {usesVenue ? (
                <>
                  <label className="field">
                    <span>Venue</span>
                    <select
                      value={form.facilityId}
                      onChange={(event) => setForm((current) => ({ ...current, facilityId: event.target.value, resourceId: '' }))}
                    >
                      <option value="">Choose a venue…</option>
                      {venues.data?.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name} — {item.location.city.name}
                          {item.isDemo ? ' (demo)' : ''}
                        </option>
                      ))}
                    </select>
                    {venues.data?.length === 0 && <small>No listed venue supports {sport.name} yet. Use “Somewhere else”.</small>}
                  </label>
                  {form.facilityId && bookable.length > 0 && (
                    <label className="field">
                      <span>Reserve a space for this time (optional)</span>
                      <select value={form.resourceId} onChange={(event) => set('resourceId', event.target.value)}>
                        <option value="">Don’t reserve — I’ve arranged it separately</option>
                        {bookable.map((item) => (
                          <option key={item.id} value={item.id}>
                            {item.name} · {item.hourlyRateCentavos ? `${peso(item.hourlyRateCentavos)}/hr` : 'free'}
                          </option>
                        ))}
                      </select>
                      {reserving && (
                        <small>
                          {reserving.name} is booked in your name for the session’s time, following the venue’s rules. If it is taken, the session is not created.
                        </small>
                      )}
                    </label>
                  )}
                </>
              ) : (
                <>
                  <CityPicker value={city} onChange={setCity} />
                  <label className="field">
                    <span>{sport.matchFormat.usesRoutes ? 'Meet-up point' : 'Place name'}</span>
                    <input value={form.venueName} onChange={(event) => set('venueName', event.target.value)} maxLength={160} placeholder={sport.matchFormat.usesRoutes ? 'e.g. Main gate, north side' : 'e.g. Barangay covered court'} />
                  </label>
                  {sport.matchFormat.usesRoutes && (
                    <div className="field-pair">
                      <label className="field">
                        <span>Route name</span>
                        <input value={form.routeName} onChange={(event) => set('routeName', event.target.value)} maxLength={160} />
                      </label>
                      <label className="field">
                        <span>Distance (km)</span>
                        <input type="number" min={0.1} max={1000} step={0.1} value={form.routeKm} onChange={(event) => set('routeKm', event.target.value)} />
                      </label>
                    </div>
                  )}
                </>
              )}
              <label className="field">
                <span>Meet-up note (optional)</span>
                <input value={form.meetupNote} onChange={(event) => set('meetupNote', event.target.value)} maxLength={500} placeholder="e.g. Look for the lime banner" />
              </label>
            </fieldset>

            <fieldset>
              <legend>Who</legend>
              <div className="field-pair">
                <label className="field">
                  <span>Player limit</span>
                  <input type="number" min={1} max={1000} value={form.capacity} onChange={(event) => set('capacity', Math.max(1, Number(event.target.value) || 1))} />
                </label>
                <label className="field">
                  <span>Minimum to go ahead</span>
                  <input type="number" min={1} max={form.capacity} value={form.minPlayers} onChange={(event) => set('minPlayers', Math.max(1, Number(event.target.value) || 1))} />
                </label>
                <label className="field">
                  <span>Fee per player (₱)</span>
                  <input type="number" min={0} step={10} value={form.fee} onChange={(event) => set('fee', Math.max(0, Number(event.target.value) || 0))} />
                </label>
                <label className="field">
                  <span>Who can join</span>
                  <select value={form.joinPolicy} onChange={(event) => set('joinPolicy', event.target.value as 'open' | 'approval')}>
                    <option value="open">Anyone, first come first served</option>
                    <option value="approval">I approve each request</option>
                  </select>
                </label>
              </div>
              <label className="check">
                <input type="checkbox" checked={form.hostPlays} onChange={(event) => set('hostPlays', event.target.checked)} /> I’m playing too (takes one place)
              </label>
              <p className="form-hint">When the session fills up, extra players join a waitlist and move up automatically as places open.</p>
            </fieldset>

            {sport.queueEligible && (
              <fieldset>
                <legend>Queue</legend>
                <div className="field-pair">
                  <label className="field">
                    <span>How games rotate</span>
                    <select value={queueMode} onChange={(event) => set('queueMode', event.target.value as QueueMode)}>
                      <option value="none">{QUEUE_LABELS.none}</option>
                      {sport.matchFormat.queueModes.map((mode) => (
                        <option key={mode} value={mode}>
                          {QUEUE_LABELS[mode]}
                        </option>
                      ))}
                    </select>
                  </label>
                  {queueMode !== 'none' && (
                    <label className="field">
                      <span>Courts in play</span>
                      <input type="number" min={1} max={30} value={form.courtsInPlay} onChange={(event) => set('courtsInPlay', Math.max(1, Number(event.target.value) || 1))} />
                    </label>
                  )}
                </div>
              </fieldset>
            )}

            {error && (
              <p className="form-error" role="alert">
                {error}
              </p>
            )}
            <button className="button button-primary button-block" disabled={busy || form.title.trim().length < 3}>
              {busy ? 'Publishing…' : form.repeatWeeks > 1 ? `Publish ${form.repeatWeeks} sessions` : 'Publish session'}
            </button>
          </>
        )}
      </form>
    </div>
  )
}
