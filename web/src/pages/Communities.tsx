import { MapPin, Plus, UsersRound } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { CityPicker } from '../components/CityPicker'
import { Modal } from '../components/Modal'
import { SportIcon } from '../components/SportIcon'
import { DemoBadge, EmptyState, ErrorState, Loading } from '../components/StateViews'
import { ApiError, api } from '../lib/api'
import { plural } from '../lib/format'
import type { Community, Place } from '../lib/types'
import { useAsync } from '../lib/useAsync'
import { useAuth } from '../state/auth'
import { useCatalog } from '../state/catalog'
import { placeLabel, placeParams, usePlace } from '../state/place'
import { useToast } from '../state/toast'

function CommunityCard({ community }: { community: Community }) {
  return (
    <Link to={`/communities/${community.slug}`} className="card community-card">
      <div className="card-top">
        <span className="sport-badge">{plural(community.memberCount, 'member')}</span>
        <div className="badge-line">
          {community.viewerRole && <span className="status-badge status-confirmed">{community.viewerRole === 'member' ? 'Joined' : 'Organiser'}</span>}
          {community.isDemo && <DemoBadge />}
        </div>
      </div>
      <h3>{community.name}</h3>
      <p className="meta-line">
        <MapPin size={15} /> {community.city?.name ?? 'Anywhere in the Philippines'}
      </p>
      <div className="sport-strip">
        {community.sports.map((sport) => (
          <span key={sport.id} title={sport.name}>
            <SportIcon sport={sport} size="sm" />
          </span>
        ))}
        <small>{community.sports.map((sport) => sport.name).join(', ')}</small>
      </div>
    </Link>
  )
}

export function Communities() {
  const { user, requireAuth } = useAuth()
  const { sports } = useCatalog()
  const { place, openPicker } = usePlace()
  const [scope, setScope] = useState<'all' | 'mine'>('all')
  const [sportId, setSportId] = useState('')
  const [creating, setCreating] = useState(false)
  const area = useMemo(() => placeParams(place), [place])
  const mine = scope === 'mine' && Boolean(user)
  const communities = useAsync(
    () => api.communities(mine ? { mine: true, sportId: sportId || undefined } : { ...area, sportId: sportId || undefined }),
    [mine, sportId, JSON.stringify(area), user?.id],
  )
  // Only offer sports that at least one listed community plays.
  const sportsHere = sports.filter((sport) => sportId === sport.id || communities.data?.some((item) => item.sports.some((entry) => entry.id === sport.id)))

  return (
    <div className="page">
      <div className="page-title stats-title">
        <div>
          <span className="eyebrow">BUILD YOUR CIRCLE</span>
          <h1>Communities</h1>
          <p>Clubs, barkadas and teams that play together{scope === 'all' && ` · ${placeLabel(place)}`}.</p>
        </div>
        <button className="button button-primary" onClick={() => requireAuth('Sign in to start a community.', () => setCreating(true))}>
          <Plus size={17} /> Start a community
        </button>
      </div>

      <div className="toolbar">
        <div className="segmented" role="tablist">
          <button role="tab" aria-selected={scope === 'all'} className={scope === 'all' ? 'active' : ''} onClick={() => setScope('all')}>
            Discover
          </button>
          <button role="tab" aria-selected={scope === 'mine'} className={scope === 'mine' ? 'active' : ''} onClick={() => requireAuth('Sign in to see your communities.', () => setScope('mine'))}>
            Mine
          </button>
        </div>
        {scope === 'all' && (
          <button className="button button-ghost button-small" onClick={openPicker}>
            <MapPin size={15} /> {placeLabel(place)}
          </button>
        )}
      </div>

      {sportsHere.length > 1 && (
        <div className="filters" aria-label="Sport">
          <button aria-pressed={!sportId} className={!sportId ? 'active' : ''} onClick={() => setSportId('')}>
            All sports
          </button>
          {sportsHere.map((sport) => (
            <button key={sport.id} aria-pressed={sportId === sport.id} className={sportId === sport.id ? 'active' : ''} onClick={() => setSportId(sport.id)}>
              <SportIcon sport={sport} size="sm" /> {sport.name}
            </button>
          ))}
        </div>
      )}

      {communities.error && !communities.data ? (
        <ErrorState error={communities.error} onRetry={communities.reload} />
      ) : !communities.data ? (
        <Loading />
      ) : communities.data.length === 0 ? (
        <EmptyState
          icon={<UsersRound size={24} />}
          title={scope === 'mine' ? 'You haven’t joined a community yet' : 'No communities here yet'}
          action={
            <button className="button button-primary" onClick={() => requireAuth('Sign in to start a community.', () => setCreating(true))}>
              Start one
            </button>
          }
        >
          {scope === 'mine' ? 'Join one from Discover, or start your own.' : `Be the first to bring players together in ${placeLabel(place)}.`}
        </EmptyState>
      ) : (
        <div className="card-grid">
          {communities.data.map((community) => (
            <CommunityCard key={community.id} community={community} />
          ))}
        </div>
      )}

      {creating && <CreateCommunity onClose={() => setCreating(false)} />}
    </div>
  )
}

function CreateCommunity({ onClose }: { onClose: () => void }) {
  const { sports } = useCatalog()
  const { user } = useAuth()
  const navigate = useNavigate()
  const notify = useToast()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [city, setCity] = useState<Place | null>(user?.city ?? null)
  const [sportIds, setSportIds] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function create() {
    setBusy(true)
    setError('')
    try {
      const community = await api.createCommunity({ name: name.trim(), description: description.trim(), cityCode: city?.code, sportIds })
      notify('Your community is live.')
      navigate(`/communities/${community.slug}`)
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'Could not create the community.')
      setBusy(false)
    }
  }

  return (
    <Modal title="Start a community" onClose={onClose} wide>
      <div className="form">
        <label className="field">
          <span>Name</span>
          <input value={name} onChange={(event) => setName(event.target.value)} minLength={3} maxLength={120} />
        </label>
        <label className="field">
          <span>What is it about?</span>
          <textarea rows={3} maxLength={2000} value={description} onChange={(event) => setDescription(event.target.value)} />
        </label>
        <CityPicker value={city} onChange={setCity} label="Home city or municipality (optional)" />
        <div className="field">
          <span>Sports</span>
          <div className="chip-row">
            {sports.map((sport) => {
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
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button className="button button-primary button-block" onClick={create} disabled={busy || name.trim().length < 3 || sportIds.length === 0}>
          {busy ? 'Creating…' : 'Create community'}
        </button>
      </div>
    </Modal>
  )
}
