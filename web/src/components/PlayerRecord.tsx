import { Medal, Plus, Share2, Trash2, Trophy } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { ApiError, api } from '../lib/api'
import { dateKey, formatMediumDate, manilaClock, manilaIso } from '../lib/format'
import { scoreLine, sideNames } from '../lib/sessionText'
import { storyFromStats } from '../lib/story'
import type { Me, PlayerStats, Sport } from '../lib/types'
import { useAsync } from '../lib/useAsync'
import { useCatalog } from '../state/catalog'
import { useToast } from '../state/toast'
import { Modal } from './Modal'
import { SportIcon } from './SportIcon'
import { Avatar, DemoBadge, EmptyState, ErrorState, Loading } from './StateViews'
import { StoryModal } from './StoryModal'

const EMPTY_COPY = {
  matches: 'Results recorded in sessions you play in will build your record here.',
  activities: 'Log a result and your totals and bests will appear here.',
  attendance: 'Check in at a session; once it finishes it counts toward your record.',
}

function headline(stats: PlayerStats): { label: string; value: string; note: string; percent: number } {
  if (stats.recordType === 'matches') {
    const rate = stats.summary.find((item) => item.key === 'win_rate')
    const matches = stats.summary.find((item) => item.key === 'matches')
    return { label: 'WIN RATE', value: rate?.display ?? '0%', note: `${matches?.display ?? 0} matches`, percent: rate?.value ?? 0 }
  }
  const lead = stats.recordType === 'activities' ? (stats.summary.find((item) => item.unit) ?? stats.summary[0]) : stats.summary[0]
  return { label: lead.label.toUpperCase(), value: lead.display, note: lead.unit, percent: 100 }
}

function recordSentence(stats: PlayerStats): string {
  if (stats.recordType !== 'matches') return 'Every entry here was logged or checked in. Nothing is estimated.'
  if (stats.streakType === 'W' && stats.streak > 1) return `You’ve won your last ${stats.streak} matches.`
  if (stats.streakType === 'L' && stats.streak > 1) return `${stats.streak} losses in a row. The next one starts a new run.`
  return 'Your record is built from scores recorded in sessions.'
}

/** One player's records, sport by sport. Each sport shows only what its own results can support. */
export function PlayerRecord({ user }: { user: Me }) {
  const { sport: findSport } = useCatalog()
  const notify = useToast()
  const records = useAsync(() => api.records(), [user.id])
  const achievements = useAsync(() => api.achievements(), [user.id])
  const [chosen, setChosen] = useState<string | null>(null)
  const [story, setStory] = useState(false)
  const [logging, setLogging] = useState(false)

  // Sports with results first, then sports on the profile that have none yet.
  const withResults = (records.data ?? []).map((item) => item.sport.id)
  const sportIds = [...withResults, ...user.sports.map((item) => item.sportId).filter((id) => !withResults.includes(id))]
  const sportId = chosen ?? sportIds[0] ?? null
  const sport = findSport(sportId)
  const stats = useAsync(() => api.stats(sportId ?? undefined), [sportId, user.id], Boolean(sportId))
  const isMatches = stats.data?.recordType === 'matches'
  const matches = useAsync(() => api.myMatches(sportId ?? '', 8), [sportId, user.id, stats.data?.recordType], Boolean(sportId) && isMatches)
  const activities = useAsync(
    () => api.myActivities(sportId ?? '', 8),
    [sportId, user.id, stats.data?.recordType],
    Boolean(sportId) && stats.data?.recordType === 'activities',
  )

  if (records.error && !records.data) return <ErrorState error={records.error} onRetry={records.reload} />
  if (!records.data) return <Loading label="Loading your record…" />

  if (!sportId) {
    return (
      <EmptyState icon={<Trophy size={24} />} title="No records yet">
        Add the sports you play to your profile, join a session and your results will collect here, one record per sport.
      </EmptyState>
    )
  }

  const data = stats.data
  const skill = user.sports.find((item) => item.sportId === sportId)?.skillLevel ?? ''
  const canLog = Boolean(sport && sport.scoringConfig.activityFields.length > 0)

  async function removeActivity(id: string) {
    try {
      await api.deleteActivity(id)
      notify('Entry removed.')
      activities.reload()
      stats.reload()
      records.reload()
    } catch (error) {
      notify(error instanceof ApiError ? error.message : 'Could not remove that entry.', 'error')
    }
  }

  return (
    <section className="stats-page">
      <div className="section-heading">
        <div>
          <span className="eyebrow">PLAYER RECORD</span>
          <h2>{sport?.name ?? 'Your record'}</h2>
        </div>
        <div className="button-row">
          {canLog && (
            <button className="button button-ghost button-small" onClick={() => setLogging(true)}>
              <Plus size={16} /> Log a result
            </button>
          )}
          {data?.hasData && (
            <button className="share-button" onClick={() => setStory(true)}>
              <Share2 size={17} /> Share card
            </button>
          )}
        </div>
      </div>

      {sportIds.length > 1 && (
        <div className="filters" role="tablist" aria-label="Sport">
          {sportIds.map((id) => {
            const item = findSport(id)
            if (!item) return null
            return (
              <button key={id} role="tab" aria-selected={id === sportId} className={id === sportId ? 'active' : ''} onClick={() => setChosen(id)}>
                <SportIcon sport={item} size="sm" /> {item.name}
              </button>
            )
          })}
        </div>
      )}

      {stats.error && !data ? (
        <ErrorState error={stats.error} onRetry={stats.reload} />
      ) : !data ? (
        <Loading />
      ) : !data.hasData ? (
        <EmptyState
          icon={<Trophy size={24} />}
          title={`No ${data.sport.name.toLowerCase()} results yet`}
          action={
            canLog ? (
              <button className="button button-primary" onClick={() => setLogging(true)}>
                <Plus size={16} /> Log your first result
              </button>
            ) : (
              <Link to={`/?sport=${data.sport.id}#sessions`} className="button button-primary">
                Find a session
              </Link>
            )
          }
        >
          {EMPTY_COPY[data.recordType]}
        </EmptyState>
      ) : (
        <>
          <section className="record-hero">
            <div className="rating-ring" style={{ background: `conic-gradient(var(--lime) 0 ${headline(data).percent}%, rgba(255,255,255,.13) ${headline(data).percent}%)` }}>
              <div>
                <span>{headline(data).label}</span>
                <strong>{headline(data).value}</strong>
                <small>{headline(data).note}</small>
              </div>
            </div>
            <div className="record-copy">
              <span className="eyebrow light">
                {[data.sport.name, skill].filter(Boolean).join(' · ').toUpperCase()} {data.containsDemoData && <DemoBadge label="Demo data" />}
              </span>
              <h2>{isMatches && data.streakType === 'W' && data.streak > 1 ? 'Your game is moving up.' : 'Your record so far.'}</h2>
              <p>{recordSentence(data)}</p>
              {data.recentForm.length > 0 && (
                <div className="form-row" aria-label={`Last ${data.recentForm.length} results: ${data.recentForm.join(', ')}`}>
                  <span>LAST {data.recentForm.length}</span>
                  {data.recentForm.map((result, index) => (
                    <i className={result === 'W' ? 'win' : 'loss'} key={index}>
                      {result}
                    </i>
                  ))}
                </div>
              )}
            </div>
            <Trophy className="record-trophy" size={110} strokeWidth={1.1} />
          </section>

          <div className="stat-grid">
            {data.summary.map((item) => (
              <div className="stat-card" key={item.key}>
                <strong>
                  {item.display}
                  {item.unit && item.unit !== '%' && <em> {item.unit}</em>}
                </strong>
                <span>{item.label}</span>
                {item.note && <small>{item.note}</small>}
              </div>
            ))}
          </div>

          <div className="stats-lower">
            <section className="chart-card">
              <div className="section-heading">
                <div>
                  <span className="eyebrow">ACTIVITY</span>
                  <h3>{isMatches ? 'Matches' : data.recordType === 'activities' ? 'Entries' : 'Sessions'} by month</h3>
                </div>
              </div>
              <MonthChart months={data.byMonth} />
            </section>
            <section className="achievement-card">
              {data.partners.length > 0 ? (
                <>
                  <span className="eyebrow">PLAYED WITH MOST</span>
                  <ul className="partner-list">
                    {data.partners.map((partner) => (
                      <li key={partner.user.id}>
                        <Avatar user={partner.user} size={32} />
                        <div>
                          <strong>{partner.user.displayName}</strong>
                          <small>
                            {partner.matches} together · {partner.wins} won
                          </small>
                        </div>
                      </li>
                    ))}
                  </ul>
                </>
              ) : (
                <>
                  <span className="eyebrow">BEST RUN</span>
                  <div className="badge-medal">
                    <Medal size={35} />
                  </div>
                  <h3>{data.bestWinStreak > 1 ? `${data.bestWinStreak} wins in a row` : 'Keep showing up'}</h3>
                  <p>{data.bestWinStreak > 1 ? 'Your longest winning streak.' : 'Every recorded result adds to this page.'}</p>
                </>
              )}
            </section>
          </div>

          {isMatches && (matches.data?.length ?? 0) > 0 && (
            <section className="section-block">
              <div className="section-heading">
                <h3>Recent matches</h3>
              </div>
              <div className="history-list">
                {matches.data?.map((match) => (
                  <div key={match.id} className="history-row">
                    <i className={`result-chip result-${match.result}`}>{match.result}</i>
                    <div>
                      <strong>
                        {sideNames(match, match.mySide)} <span>vs</span> {sideNames(match, match.mySide === 1 ? 2 : 1)}
                      </strong>
                      <small>
                        {match.completedAt && formatMediumDate(match.completedAt)} {match.isDemo && '· demo'}
                      </small>
                    </div>
                    <b>{scoreLine(match)}</b>
                  </div>
                ))}
              </div>
            </section>
          )}

          {data.recordType === 'activities' && (activities.data?.length ?? 0) > 0 && sport && (
            <section className="section-block">
              <div className="section-heading">
                <h3>Recent entries</h3>
              </div>
              <div className="history-list">
                {activities.data?.map((entry) => (
                  <div key={entry.id} className="history-row">
                    <SportIcon sport={entry.sport} size="sm" />
                    <div>
                      <strong>
                        {sport.scoringConfig.activityFields
                          .filter((field) => field.key in entry.metrics)
                          .map((field) => `${entry.metrics[field.key]} ${field.unit}`)
                          .join(' · ')}
                      </strong>
                      <small>
                        {formatMediumDate(entry.occurredAt)} {entry.isDemo ? '· demo' : '· self-reported'}
                      </small>
                    </div>
                    {!entry.isDemo && (
                      <button className="icon-button" onClick={() => removeActivity(entry.id)} aria-label="Remove this entry">
                        <Trash2 size={16} />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}
        </>
      )}

      {(achievements.data?.length ?? 0) > 0 && (
        <section className="section-block">
          <div className="section-heading">
            <h3>Achievements</h3>
          </div>
          <div className="badge-row">
            {achievements.data?.map((badge) => (
              <div key={badge.id}>
                <span>
                  <Medal size={22} />
                </span>
                <div>
                  <strong>{badge.label}</strong>
                  <small>{badge.description}</small>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {story && data?.hasData && <StoryModal data={storyFromStats(data, user.displayName, skill)} onClose={() => setStory(false)} />}
      {logging && sport && (
        <LogActivity
          sport={sport}
          onClose={() => setLogging(false)}
          onSaved={() => {
            setLogging(false)
            notify('Logged.')
            stats.reload()
            activities.reload()
            records.reload()
            achievements.reload()
          }}
        />
      )}
    </section>
  )
}

function MonthChart({ months }: { months: PlayerStats['byMonth'] }) {
  const peak = Math.max(1, ...months.map((month) => month.count))
  return (
    <div className="bar-chart" role="img" aria-label={months.map((month) => `${month.label}: ${month.count}`).join(', ')}>
      {months.map((month, index) => (
        <div key={month.month}>
          <em>{month.count || ''}</em>
          <span className={index === months.length - 1 ? 'current' : ''} style={{ height: `${Math.max(month.count ? 6 : 0, (month.count / peak) * 100)}%` }} />
          <small>{month.label}</small>
        </div>
      ))}
    </div>
  )
}

/** A form generated from the sport's own activity fields. */
function LogActivity({ sport, onClose, onSaved }: { sport: Sport; onClose: () => void; onSaved: () => void }) {
  const fields = sport.scoringConfig.activityFields
  const [values, setValues] = useState<Record<string, string>>({})
  const [day, setDay] = useState(dateKey())
  const [time, setTime] = useState(() => manilaClock(new Date().toISOString()))
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function save() {
    const metrics: Record<string, number> = {}
    for (const field of fields) {
      const raw = values[field.key]
      if (raw === undefined || raw === '') {
        if (field.required) return setError(`${field.label} is required.`)
        continue
      }
      metrics[field.key] = Number(raw)
    }
    setBusy(true)
    setError('')
    try {
      await api.logActivity({ sportId: sport.id, occurredAt: manilaIso(day, time), metrics, note: note.trim() })
      onSaved()
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'Could not save. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title={`Log ${sport.name.toLowerCase()}`} onClose={onClose}>
      <div className="form">
        {fields.map((field) => (
          <label className="field" key={field.key}>
            <span>
              {field.label}
              {field.unit && ` (${field.unit})`}
              {!field.required && ' — optional'}
            </span>
            <input
              type="number"
              inputMode="decimal"
              min={field.min ?? undefined}
              max={field.max ?? undefined}
              step={field.type === 'integer' ? 1 : 'any'}
              value={values[field.key] ?? ''}
              onChange={(event) => setValues((current) => ({ ...current, [field.key]: event.target.value }))}
            />
          </label>
        ))}
        <div className="field-pair">
          <label className="field">
            <span>Date</span>
            <input type="date" value={day} max={dateKey()} onChange={(event) => setDay(event.target.value)} />
          </label>
          <label className="field">
            <span>Time (Philippine time)</span>
            <input type="time" value={time} onChange={(event) => setTime(event.target.value)} />
          </label>
        </div>
        <label className="field">
          <span>Note (optional)</span>
          <input value={note} onChange={(event) => setNote(event.target.value)} maxLength={300} />
        </label>
        <p className="form-hint">This is saved as self-reported. Log what you actually did; your totals and bests are worked out from these entries.</p>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button className="button button-primary button-block" onClick={save} disabled={busy}>
          {busy ? 'Saving…' : 'Save'}
        </button>
      </div>
    </Modal>
  )
}
