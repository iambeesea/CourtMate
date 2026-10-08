import { ArrowRight, Building2, CalendarSearch, List, Map as MapIcon, MapPin, Plus, UsersRound } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { FacilityCard } from '../components/FacilityCard'
import { LazyMap } from '../components/LazyMap'
import { SportIcon } from '../components/SportIcon'
import { EmptyState, ErrorState } from '../components/StateViews'
import { SessionCard } from '../components/SessionCard'
import { api } from '../lib/api'
import { addDays, dateKey, formatLongDate, manilaIso, placeLine, plural, weekdayOf } from '../lib/format'
import type { Session } from '../lib/types'
import { useAsync } from '../lib/useAsync'
import { useCatalog } from '../state/catalog'
import { placeLabel, placeParams, usePlace } from '../state/place'

type When = 'any' | 'today' | 'week' | 'weekend'

const WHEN_LABELS: Record<When, string> = { any: 'Any time', today: 'Today', week: 'Next 7 days', weekend: 'This weekend' }

/** Start-time window for a "when" filter, as UTC instants for Manila calendar days. */
function whenWindow(when: When): { startsAfter?: string; startsBefore?: string } {
  const today = dateKey()
  if (when === 'today') return { startsBefore: manilaIso(addDays(today, 1), '00:00') }
  if (when === 'week') return { startsBefore: manilaIso(addDays(today, 7), '00:00') }
  if (when === 'weekend') {
    const weekday = weekdayOf(today)
    const saturday = weekday === 6 ? addDays(today, -1) : addDays(today, 5 - weekday)
    return { startsAfter: manilaIso(saturday, '00:00'), startsBefore: manilaIso(addDays(saturday, 2), '00:00') }
  }
  return {}
}

export function Explore() {
  const { sports, categories, loading: catalogLoading, error: catalogError, reload, sport: findSport } = useCatalog()
  const { place, openPicker } = usePlace()
  const [params, setParams] = useSearchParams()
  const [category, setCategory] = useState('all')
  const [view, setView] = useState<'list' | 'map'>('list')
  const sportId = params.get('sport') ?? ''
  const sport = findSport(sportId)
  const area = useMemo(() => placeParams(place), [place])

  const facilities = useAsync(
    (signal) => api.facilities({ ...area, sportId: sportId || undefined, limit: 60 }, signal),
    [JSON.stringify(area), sportId],
    !sport || sport.bookingEligible,
  )
  const [when, setWhen] = useState<When>('any')
  const [onlyOpen, setOnlyOpen] = useState(false)
  const [onlyFree, setOnlyFree] = useState(false)
  const sessions = useAsync(
    (signal) =>
      api.sessions({ ...area, ...whenWindow(when), sportId: sportId || undefined, hasSpots: onlyOpen || undefined, free: onlyFree || undefined, limit: 60 }, signal),
    [JSON.stringify(area), sportId, when, onlyOpen, onlyFree],
  )

  function replaceSession(updated: Session) {
    sessions.setData((current) => current?.map((item) => (item.id === updated.id ? { ...item, ...updated } : item)))
  }

  const visibleSports = sports.filter((item) => category === 'all' || item.categoryId === category)
  const points = (facilities.data ?? [])
    .filter((item) => item.latitude !== null && item.longitude !== null)
    .map((item) => ({
      id: item.id,
      latitude: item.latitude as number,
      longitude: item.longitude as number,
      title: item.name,
      subtitle: placeLine(item.location),
      href: `/venues/${item.slug}`,
      tone: 'venue' as const,
    }))
  const sessionPoints = (sessions.data ?? [])
    .filter((item) => item.latitude !== null && item.longitude !== null)
    .map((item) => ({
      id: `session-${item.id}`,
      latitude: item.latitude as number,
      longitude: item.longitude as number,
      title: item.title,
      subtitle: `${item.sport.name} · ${item.venueName}`,
      href: `/sessions/${item.id}`,
      tone: 'session' as const,
    }))

  function chooseSport(id: string) {
    const next = new URLSearchParams(params)
    if (id && id !== sportId) next.set('sport', id)
    else next.delete('sport')
    setParams(next, { replace: true })
  }

  if (catalogError) {
    return (
      <div className="page">
        <ErrorState error={catalogError} onRetry={reload} />
      </div>
    )
  }

  return (
    <div className="page discover-page">
      <section className="welcome-row">
        <div>
          <span className="eyebrow">{formatLongDate(new Date()).toUpperCase()}</span>
          <h1>Find your next game.</h1>
          <p>Open plays, courts, fields, lanes and classes across the Philippines.</p>
        </div>
        <button className="place-chip" onClick={openPicker}>
          <MapPin size={18} />
          <div>
            <strong>{placeLabel(place)}</strong>
            <span>Change location</span>
          </div>
        </button>
      </section>

      <section className="hero-banner">
        <div className="hero-copy">
          <span className="hero-label">ONE APP, EVERY SPORT</span>
          <h2>
            Discover. Reserve.
            <br />
            Play. Repeat.
          </h2>
          <p>Pick a sport to see where you can play it, who is hosting, and which courts, fields, lanes or studios are open.</p>
          <a href="#sessions" className="hero-cta">
            Find a game <ArrowRight size={17} />
          </a>
        </div>
        <div className="court-illustration" aria-hidden="true">
          <div className="court-net" />
          <div className="ball ball-one" />
          <div className="ball ball-two" />
          <div className="paddle paddle-one" />
          <div className="paddle paddle-two" />
        </div>
      </section>

      <section className="section-block">
        <div className="section-heading">
          <div>
            <span className="eyebrow">CHOOSE A SPORT</span>
            <h2>{sport ? sport.name : 'All sports'}</h2>
          </div>
          {sport && (
            <button className="text-button" onClick={() => chooseSport('')}>
              Clear
            </button>
          )}
        </div>
        <div className="filters" role="tablist" aria-label="Sport categories">
          <button role="tab" aria-selected={category === 'all'} className={category === 'all' ? 'active' : ''} onClick={() => setCategory('all')}>
            All
          </button>
          {categories.map((item) => (
            <button key={item.id} role="tab" aria-selected={category === item.id} className={category === item.id ? 'active' : ''} onClick={() => setCategory(item.id)}>
              {item.name}
            </button>
          ))}
        </div>
        <div className="sport-grid">
          {catalogLoading
            ? Array.from({ length: 8 }, (_, index) => <div key={index} className="sport-tile skeleton" />)
            : visibleSports.map((item) => (
                <button key={item.id} className={`sport-tile ${item.id === sportId ? 'active' : ''}`} aria-pressed={item.id === sportId} onClick={() => chooseSport(item.id)}>
                  <SportIcon sport={item} />
                  <span>{item.name}</span>
                </button>
              ))}
        </div>
      </section>

      <section className="section-block" id="sessions">
        <div className="section-heading">
          <div>
            <span className="eyebrow">OPEN PLAY · {placeLabel(place).toUpperCase()}</span>
            <h2>{sport ? `${sport.name} sessions` : 'Open sessions'}</h2>
          </div>
          <Link to={`/host${sportId ? `?sport=${sportId}` : ''}`} className="button button-primary button-small">
            <Plus size={16} /> Host
          </Link>
        </div>
        <div className="filters" aria-label="Session filters">
          {(Object.keys(WHEN_LABELS) as When[]).map((value) => (
            <button key={value} aria-pressed={when === value} className={when === value ? 'active' : ''} onClick={() => setWhen(value)}>
              {WHEN_LABELS[value]}
            </button>
          ))}
          <button aria-pressed={onlyOpen} className={`filter-toggle ${onlyOpen ? 'active' : ''}`} onClick={() => setOnlyOpen((value) => !value)}>
            Has spots
          </button>
          <button aria-pressed={onlyFree} className={`filter-toggle ${onlyFree ? 'active' : ''}`} onClick={() => setOnlyFree((value) => !value)}>
            Free
          </button>
        </div>
        {sessions.error && !sessions.data ? (
          <ErrorState error={sessions.error} onRetry={sessions.reload} />
        ) : sessions.loading && !sessions.data ? (
          <div className="session-grid">
            {[1, 2, 3].map((item) => (
              <div key={item} className="session-card skeleton" />
            ))}
          </div>
        ) : !sessions.data?.length ? (
          <EmptyState
            icon={<CalendarSearch size={24} />}
            title="No sessions match"
            action={
              <Link to={`/host${sportId ? `?sport=${sportId}` : ''}`} className="button button-primary">
                Host the first one
              </Link>
            }
          >
            Nobody is hosting {sport ? sport.name.toLowerCase() : 'a session'} in {placeLabel(place)} for that time yet. Try a wider area or another day.
          </EmptyState>
        ) : (
          <div className={`session-grid ${sessions.loading ? 'is-refreshing' : ''}`}>
            {sessions.data.map((session) => (
              <SessionCard key={session.id} session={session} onChanged={replaceSession} />
            ))}
          </div>
        )}
      </section>

      <section className="section-block" id="venues">
        <div className="section-heading">
          <div>
            <span className="eyebrow">{placeLabel(place).toUpperCase()}</span>
            <h2>{sport ? `${sport.name} venues` : 'Venues'}</h2>
          </div>
          {(!sport || sport.bookingEligible) && (
            <div className="segmented segmented-small" role="tablist" aria-label="Venue view">
              <button role="tab" aria-selected={view === 'list'} className={view === 'list' ? 'active' : ''} onClick={() => setView('list')}>
                <List size={15} /> List
              </button>
              <button role="tab" aria-selected={view === 'map'} className={view === 'map' ? 'active' : ''} onClick={() => setView('map')}>
                <MapIcon size={15} /> Map
              </button>
            </div>
          )}
        </div>

        {sport && !sport.bookingEligible ? (
          <EmptyState icon={<MapPin size={24} />} title={`${sport.name} doesn’t need a booked venue`}>
            {sport.name} sessions meet at a route or a public spot, so there is nothing to reserve. Look for hosted sessions instead.
          </EmptyState>
        ) : facilities.error && !facilities.data ? (
          <ErrorState error={facilities.error} onRetry={facilities.reload} />
        ) : facilities.loading && !facilities.data ? (
          <div className="card-grid">
            {[1, 2, 3].map((item) => (
              <div key={item} className="card skeleton facility-skeleton" />
            ))}
          </div>
        ) : !facilities.data?.length ? (
          <EmptyState
            icon={<Building2 size={24} />}
            title="No venues here yet"
            action={
              <button className="button button-primary" onClick={openPicker}>
                Change location
              </button>
            }
          >
            Nothing matches {sport ? sport.name.toLowerCase() : 'your search'} in {placeLabel(place)}. Try a wider area or another sport.
          </EmptyState>
        ) : view === 'map' ? (
          <>
            <LazyMap points={[...points, ...sessionPoints]} origin={place.mode === 'nearby' ? [place.lat, place.lng] : undefined} />
            <p className="form-hint">
              {plural(points.length, 'venue')} (navy pins) and {plural(sessionPoints.length, 'session')} (lime pins). Tap a pin for details.
            </p>
          </>
        ) : (
          <div className="card-grid">
            {facilities.data.map((item) => (
              <FacilityCard key={item.id} facility={item} sportId={sportId || undefined} />
            ))}
          </div>
        )}
      </section>

      <section className="community-strip">
        <div className="community-icon">
          <UsersRound size={26} />
        </div>
        <div>
          <span className="eyebrow">BUILD YOUR CIRCLE</span>
          <h3>Communities make every game better.</h3>
          <p>Meet regular partners, find skill-matched sessions, and never play alone.</p>
        </div>
      </section>
    </div>
  )
}
