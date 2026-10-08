import { ArrowLeft, MapPin, Plus, UsersRound } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { Modal } from '../components/Modal'
import { SessionCard } from '../components/SessionCard'
import { SportIcon } from '../components/SportIcon'
import { Avatar, DemoBadge, ErrorState, Loading } from '../components/StateViews'
import { ApiError, api } from '../lib/api'
import { plural } from '../lib/format'
import type { CommunityDetail, Member, Team, TeamDetail } from '../lib/types'
import { useAsync } from '../lib/useAsync'
import { useAuth } from '../state/auth'
import { useToast } from '../state/toast'

export function MemberList({ members, onRemove }: { members: Member[]; onRemove?: (member: Member) => void }) {
  return (
    <ul className="queue-list">
      {members.map((member) => (
        <li key={member.user.id}>
          <Avatar user={member.user} size={34} />
          <span className="queue-name">{member.user.displayName}</span>
          {member.role !== 'member' && <small>{member.role}</small>}
          {onRemove && member.role === 'member' && (
            <button className="button button-ghost button-small" onClick={() => onRemove(member)}>
              Remove
            </button>
          )}
        </li>
      ))}
    </ul>
  )
}

export function TeamCard({ team }: { team: Team }) {
  return (
    <Link to={`/teams/${team.id}`} className="card team-card">
      <div className="card-top">
        <span className="sport-badge">{team.sport.name}</span>
        {team.isDemo && <DemoBadge />}
      </div>
      <h3>{team.name}</h3>
      <p className="meta-line">
        <UsersRound size={15} /> {plural(team.memberCount, 'player')} · captain {team.captain.displayName}
      </p>
    </Link>
  )
}

export function CommunityPage() {
  const { id = '' } = useParams()
  const { user, requireAuth } = useAuth()
  const notify = useToast()
  const community = useAsync(() => api.community(id), [id, user?.id])
  const sessions = useAsync(() => api.sessions({ communityId: community.data?.id, limit: 30 }), [community.data?.id, user?.id], Boolean(community.data))
  const [busy, setBusy] = useState(false)
  const [addingTeam, setAddingTeam] = useState(false)

  async function run(action: () => Promise<CommunityDetail>, success: string) {
    setBusy(true)
    try {
      community.setData(await action())
      notify(success)
    } catch (error) {
      notify(error instanceof ApiError ? error.message : 'That didn’t work. Please try again.', 'error')
    } finally {
      setBusy(false)
    }
  }

  if (community.error && !community.data) {
    return (
      <div className="page">
        <ErrorState error={community.error} onRetry={community.reload} />
      </div>
    )
  }
  if (!community.data) return <Loading label="Loading community…" />
  const data = community.data

  return (
    <div className="page">
      <Link to="/communities" className="back-link">
        <ArrowLeft size={16} /> Communities
      </Link>
      <header className="venue-header">
        <div className="badge-line">
          {data.isDemo && <DemoBadge label="Demo community" />}
          {data.viewerRole && <span className="status-badge status-confirmed">{data.viewerRole === 'member' ? 'You’re a member' : `You’re the ${data.viewerRole}`}</span>}
        </div>
        <h1>{data.name}</h1>
        <p className="meta-line">
          <MapPin size={16} /> {[data.city?.name, data.region?.name].filter(Boolean).join(' · ') || 'Anywhere in the Philippines'} · {plural(data.memberCount, 'member')}
        </p>
        {data.description && <p className="venue-description">{data.description}</p>}
        <div className="chip-row community-sports">
          {data.sports.map((sport) => (
            <span key={sport.id} className="chip chip-static">
              <SportIcon sport={sport} size="sm" /> {sport.name}
            </span>
          ))}
        </div>
        <div className="action-bar">
          {!data.viewerRole ? (
            <button className="button button-primary" disabled={busy} onClick={() => requireAuth('Sign in to join this community.', () => void run(() => api.joinCommunity(data.id), 'Welcome to the community!'))}>
              Join community
            </button>
          ) : (
            <>
              <Link to={`/host?sport=${data.sports[0]?.id ?? ''}`} className="button button-primary">
                <Plus size={16} /> Host a session
              </Link>
              {data.viewerRole === 'member' && (
                <button className="button button-ghost" disabled={busy} onClick={() => run(() => api.leaveCommunity(data.id), 'You left the community.')}>
                  Leave
                </button>
              )}
            </>
          )}
        </div>
      </header>

      <section className="section-block">
        <div className="section-heading">
          <h2>Upcoming sessions</h2>
        </div>
        {!sessions.data ? (
          <Loading />
        ) : sessions.data.length === 0 ? (
          <p className="notice">Nothing scheduled yet. Sessions hosted for this community will appear here.</p>
        ) : (
          <div className="session-grid">
            {sessions.data.map((session) => (
              <SessionCard key={session.id} session={session} onChanged={(updated) => sessions.setData((current) => current?.map((item) => (item.id === updated.id ? updated : item)))} />
            ))}
          </div>
        )}
      </section>

      <section className="section-block">
        <div className="section-heading">
          <h2>Teams</h2>
          {data.viewerRole && (
            <button className="button button-ghost button-small" onClick={() => setAddingTeam(true)}>
              <Plus size={15} /> New team
            </button>
          )}
        </div>
        {data.teams.length === 0 ? (
          <p className="notice">No teams yet. Members can form teams for league nights and tournaments.</p>
        ) : (
          <div className="card-grid">
            {data.teams.map((team) => (
              <TeamCard key={team.id} team={team} />
            ))}
          </div>
        )}
      </section>

      <section className="section-block people-block">
        <h3>Members · {data.members.length}</h3>
        <MemberList members={data.members} />
      </section>

      {addingTeam && (
        <CreateTeam
          community={data}
          onClose={() => setAddingTeam(false)}
          onCreated={() => {
            setAddingTeam(false)
            notify('Team created.')
            community.reload()
          }}
        />
      )}
    </div>
  )
}

function CreateTeam({ community, onClose, onCreated }: { community: CommunityDetail; onClose: () => void; onCreated: (team: TeamDetail) => void }) {
  const [name, setName] = useState('')
  const [sportId, setSportId] = useState(community.sports[0]?.id ?? '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function create() {
    setBusy(true)
    setError('')
    try {
      onCreated(await api.createTeam({ name: name.trim(), sportId, communityId: community.id, cityCode: community.city?.code, description: '' }))
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'Could not create the team.')
      setBusy(false)
    }
  }

  return (
    <Modal title="New team" onClose={onClose} variant="dialog">
      <div className="form">
        <label className="field">
          <span>Team name</span>
          <input value={name} onChange={(event) => setName(event.target.value)} minLength={2} maxLength={120} />
        </label>
        <label className="field">
          <span>Sport</span>
          <select value={sportId} onChange={(event) => setSportId(event.target.value)}>
            {community.sports.map((sport) => (
              <option key={sport.id} value={sport.id}>
                {sport.name}
              </option>
            ))}
          </select>
        </label>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button className="button button-primary button-block" onClick={create} disabled={busy || name.trim().length < 2}>
          {busy ? 'Creating…' : 'Create team'}
        </button>
      </div>
    </Modal>
  )
}
