import { ArrowLeft, MapPin } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { SportIcon } from '../components/SportIcon'
import { DemoBadge, ErrorState, Loading } from '../components/StateViews'
import { ApiError, api } from '../lib/api'
import { plural } from '../lib/format'
import type { TeamDetail } from '../lib/types'
import { useAsync } from '../lib/useAsync'
import { useAuth } from '../state/auth'
import { useToast } from '../state/toast'
import { MemberList } from './CommunityPage'

export function TeamPage() {
  const { id = '' } = useParams()
  const { user, requireAuth } = useAuth()
  const notify = useToast()
  const team = useAsync(() => api.team(id), [id, user?.id])
  const [busy, setBusy] = useState(false)

  async function run(action: () => Promise<TeamDetail>, success: string) {
    setBusy(true)
    try {
      team.setData(await action())
      notify(success)
    } catch (error) {
      notify(error instanceof ApiError ? error.message : 'That didn’t work. Please try again.', 'error')
    } finally {
      setBusy(false)
    }
  }

  if (team.error && !team.data) {
    return (
      <div className="page">
        <ErrorState error={team.error} onRetry={team.reload} />
      </div>
    )
  }
  if (!team.data) return <Loading label="Loading team…" />
  const data = team.data

  return (
    <div className="page profile-page">
      <Link to={data.community ? `/communities/${data.community.id}` : '/communities'} className="back-link">
        <ArrowLeft size={16} /> {data.community?.name ?? 'Communities'}
      </Link>
      <header className="session-header">
        <SportIcon sport={data.sport} size="lg" />
        <div>
          <div className="badge-line">
            <span className="sport-badge">{data.sport.name} team</span>
            {data.isDemo && <DemoBadge />}
          </div>
          <h1>{data.name}</h1>
          <p className="meta-line">
            <MapPin size={15} /> {data.city?.name ?? 'No home city'} · {plural(data.memberCount, 'player')}
          </p>
        </div>
      </header>
      {data.description && <p className="session-description">{data.description}</p>}
      <div className="action-bar team-actions">
        {!data.viewerRole ? (
          <button className="button button-primary" disabled={busy} onClick={() => requireAuth('Sign in to join this team.', () => void run(() => api.joinTeam(data.id), 'You’re on the team.'))}>
            Join team
          </button>
        ) : data.viewerRole === 'member' ? (
          <button className="button button-ghost" disabled={busy} onClick={() => run(() => api.leaveTeam(data.id), 'You left the team.')}>
            Leave team
          </button>
        ) : (
          <span className="status-badge status-confirmed">You’re the captain</span>
        )}
      </div>
      <section className="section-block people-block">
        <h3>Roster · {data.members.length}</h3>
        <MemberList
          members={data.members}
          onRemove={data.viewerRole === 'captain' ? (member) => void run(() => api.removeTeamMember(data.id, member.user.id), `${member.user.displayName} was removed.`) : undefined}
        />
      </section>
    </div>
  )
}
