import { Bell, CircleUserRound, LogOut, MapPin, Pencil, UsersRound } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { CityPicker } from '../components/CityPicker'
import { Modal } from '../components/Modal'
import { PlayerRecord } from '../components/PlayerRecord'
import { SportIcon } from '../components/SportIcon'
import { Avatar, DemoBadge, EmptyState, Loading } from '../components/StateViews'
import { ApiError, api } from '../lib/api'
import type { Me, Place, SportProfile } from '../lib/types'
import { useAsync } from '../lib/useAsync'
import { useAuth } from '../state/auth'
import { useCatalog } from '../state/catalog'
import { useToast } from '../state/toast'
import { TeamCard } from './CommunityPage'

export function Profile() {
  const { user, ready, openAuth, signOut } = useAuth()
  const { sport: findSport } = useCatalog()
  const notify = useToast()
  const [editing, setEditing] = useState(false)
  const teams = useAsync(() => api.teams({ mine: true }), [user?.id], Boolean(user))

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

      <div className="section-block">
        <PlayerRecord user={user} />
      </div>

      {(teams.data?.length ?? 0) > 0 && (
        <section className="section-block">
          <div className="section-heading">
            <h3>Your teams</h3>
          </div>
          <div className="card-grid">
            {teams.data?.map((team) => (
              <TeamCard key={team.id} team={team} />
            ))}
          </div>
        </section>
      )}

      <section className="section-block link-list">
        <Link to="/communities" className="link-row">
          <UsersRound size={20} />
          <div>
            <strong>Communities</strong>
            <span>Clubs and groups you play with</span>
          </div>
        </Link>
        <Link to="/notifications" className="link-row">
          <Bell size={20} />
          <div>
            <strong>Notifications</strong>
            <span>Session and booking updates</span>
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
  const [city, setCity] = useState<Place | null>(user.city)
  const [profiles, setProfiles] = useState<SportProfile[]>(user.sports)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
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
        <CityPicker value={city} onChange={setCity} label="Home city or municipality" />
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
