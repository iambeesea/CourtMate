import { BarChart3, CircleUserRound, LogOut, MapPin, Pencil } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { Modal } from '../components/Modal'
import { SportIcon } from '../components/SportIcon'
import { Avatar, DemoBadge, EmptyState, Loading } from '../components/StateViews'
import { ApiError, api } from '../lib/api'
import type { City, Me, SportProfile } from '../lib/types'
import { useAsync } from '../lib/useAsync'
import { useAuth } from '../state/auth'
import { useCatalog } from '../state/catalog'
import { useToast } from '../state/toast'

export function Profile() {
  const { user, ready, openAuth, signOut } = useAuth()
  const { sport: findSport } = useCatalog()
  const notify = useToast()
  const [editing, setEditing] = useState(false)

  if (!ready) return <Loading />
  if (!user) {
    return (
      <div className="page">
        <EmptyState
          icon={<CircleUserRound size={24} />}
          title="Your player profile"
          action={
            <div className="button-row">
              <button className="button button-primary" onClick={() => openAuth()}>
                Sign in
              </button>
              <button className="button button-ghost" onClick={() => openAuth('', 'register')}>
                Create account
              </button>
            </div>
          }
        >
          One account for every sport you play: your bookings, sessions, communities and records.
        </EmptyState>
      </div>
    )
  }

  return (
    <div className="page profile-page">
      <div className="profile-cover">
        <Avatar user={user} size={92} />
      </div>
      <div className="profile-intro">
        <div>
          <h1>
            {user.displayName} {user.isDemo && <DemoBadge label="Demo account" />}
          </h1>
          <p>
            <MapPin size={15} /> {user.city?.name ?? 'No home city set'}
          </p>
        </div>
        <button onClick={() => setEditing(true)}>
          <Pencil size={14} /> Edit profile
        </button>
      </div>
      <div className="profile-tags">
        {user.sports.length === 0 && <span>Add the sports you play</span>}
        {user.sports.map((item) => {
          const sport = findSport(item.sportId)
          return (
            <span key={item.sportId} className={item.isPrimary ? 'primary' : ''}>
              {sport && <SportIcon sport={sport} size="sm" />} {sport?.name ?? item.sportId}
              {item.skillLevel && ` · ${item.skillLevel}`}
            </span>
          )
        })}
      </div>
      {user.bio && <p className="profile-bio">{user.bio}</p>}

      <section className="section-block link-list">
        <Link to="/record" className="link-row">
          <BarChart3 size={20} />
          <div>
            <strong>Player record</strong>
            <span>Results, streaks and your shareable match card</span>
          </div>
        </Link>
        <button
          className="link-row"
          onClick={async () => {
            await signOut()
            notify('Signed out.')
          }}
        >
          <LogOut size={20} />
          <div>
            <strong>Sign out</strong>
            <span>{user.email}</span>
          </div>
        </button>
      </section>

      {editing && <EditProfile user={user} onClose={() => setEditing(false)} />}
    </div>
  )
}

function EditProfile({ user, onClose }: { user: Me; onClose: () => void }) {
  const { sports: catalog, sport: findSport } = useCatalog()
  const { setUser } = useAuth()
  const notify = useToast()
  const [displayName, setDisplayName] = useState(user.displayName)
  const [bio, setBio] = useState(user.bio)
  const [city, setCity] = useState<Pick<City, 'code' | 'name'> | null>(user.city)
  const [cityQuery, setCityQuery] = useState('')
  const [profiles, setProfiles] = useState<SportProfile[]>(user.sports)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const matches = useAsync(() => api.cities({ q: cityQuery.trim() }), [cityQuery], cityQuery.trim().length >= 2)
  const chosen = new Set(profiles.map((item) => item.sportId))

  function toggleSport(sportId: string) {
    setProfiles((current) =>
      current.some((item) => item.sportId === sportId)
        ? current.filter((item) => item.sportId !== sportId)
        : [...current, { sportId, skillLevel: '', isPrimary: current.length === 0 }],
    )
  }

  function update(sportId: string, changes: Partial<SportProfile>) {
    setProfiles((current) =>
      current.map((item) => {
        if (item.sportId === sportId) return { ...item, ...changes }
        return changes.isPrimary ? { ...item, isPrimary: false } : item
      }),
    )
  }

  async function save() {
    setBusy(true)
    setError('')
    try {
      setUser(await api.updateMe({ displayName: displayName.trim(), bio: bio.trim(), cityCode: city?.code ?? null, sports: profiles }))
      notify('Profile updated.')
      onClose()
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'Could not save. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title="Edit profile" onClose={onClose} wide>
      <div className="form">
        <label className="field">
          <span>Name shown to other players</span>
          <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} minLength={2} maxLength={80} />
        </label>
        <label className="field">
          <span>About you</span>
          <textarea value={bio} onChange={(event) => setBio(event.target.value)} maxLength={500} rows={3} />
        </label>
        <div className="field">
          <span>Home city or municipality</span>
          {city ? (
            <div className="chip-row">
              <span className="chip chip-static">{city.name}</span>
              <button className="text-button" onClick={() => setCity(null)}>
                Change
              </button>
            </div>
          ) : (
            <>
              <input value={cityQuery} onChange={(event) => setCityQuery(event.target.value)} placeholder="Type at least two letters" />
              <div className="chip-row">
                {cityQuery.trim().length >= 2 &&
                  matches.data?.slice(0, 8).map((item) => (
                    <button key={item.code} className="chip" onClick={() => setCity(item)}>
                      {item.name}
                    </button>
                  ))}
              </div>
            </>
          )}
        </div>
        <div className="field">
          <span>Sports you play</span>
          <div className="chip-row">
            {catalog.map((sport) => (
              <button key={sport.id} className={`chip ${chosen.has(sport.id) ? 'active' : ''}`} aria-pressed={chosen.has(sport.id)} onClick={() => toggleSport(sport.id)}>
                <SportIcon sport={sport} size="sm" /> {sport.name}
              </button>
            ))}
          </div>
        </div>
        {profiles.map((item) => {
          const sport = findSport(item.sportId)
          if (!sport) return null
          return (
            <div className="field-inline" key={item.sportId}>
              <strong>{sport.name}</strong>
              <select value={item.skillLevel} onChange={(event) => update(item.sportId, { skillLevel: event.target.value })} aria-label={`${sport.name} level`}>
                <option value="">Level not set</option>
                {sport.matchFormat.skillLevels
                  .filter((level) => level !== 'All levels')
                  .map((level) => (
                    <option key={level} value={level}>
                      {level}
                    </option>
                  ))}
              </select>
              <label className="check">
                <input type="radio" name="primary-sport" checked={item.isPrimary} onChange={() => update(item.sportId, { isPrimary: true })} /> Main sport
              </label>
            </div>
          )
        })}
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button className="button button-primary button-block" onClick={save} disabled={busy || displayName.trim().length < 2}>
          {busy ? 'Saving…' : 'Save profile'}
        </button>
      </div>
    </Modal>
  )
}
