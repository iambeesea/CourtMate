import { Coffee, ListOrdered, Play, Trophy, UserCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import { ApiError, api } from '../lib/api'
import { plural } from '../lib/format'
import { scoreLine, sideNames } from '../lib/sessionText'
import type { Match, MatchResult, Queue, SessionDetail, Sport } from '../lib/types'
import { useAsync } from '../lib/useAsync'
import { useAuth } from '../state/auth'
import { useToast } from '../state/toast'
import { Modal } from './Modal'
import { Avatar } from './StateViews'

const REFRESH_MS = 8000
const MODE_LABEL = { none: '', rotation: 'Rotation: everyone goes to the back after a game', winner_stays: 'Winner stays on court' }

interface QueuePanelProps {
  session: SessionDetail
  sport: Sport | undefined
  /** Called after anything that changes who is in the session, so the page can refresh. */
  onSessionChanged: () => void
}

/** The live side of a session: courts, the waiting line, check-in and results. Only shown for sports that queue. */
export function QueuePanel({ session, sport, onSessionChanged }: QueuePanelProps) {
  const { user } = useAuth()
  const notify = useToast()
  const queue = useAsync((signal) => api.queue(session.id, signal), [session.id, session.status])
  const results = useAsync(() => api.sessionMatches(session.id), [session.id, session.status])
  const [busy, setBusy] = useState(false)
  const [scoring, setScoring] = useState<Match | null>(null)
  const live = session.status === 'live'
  const { reload: reloadQueue } = queue

  // Other players' phones change the queue, so keep it fresh while the session is live.
  useEffect(() => {
    if (!live) return
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') reloadQueue()
    }, REFRESH_MS)
    return () => window.clearInterval(timer)
  }, [live, reloadQueue])

  async function run(action: () => Promise<Queue | unknown>, success?: string) {
    setBusy(true)
    try {
      const outcome = await action()
      if (outcome && typeof outcome === 'object' && 'waiting' in outcome) queue.setData(outcome as Queue)
      else queue.reload()
      if (success) notify(success)
    } catch (error) {
      notify(error instanceof ApiError ? error.message : 'That didn’t work. Please try again.', 'error')
      queue.reload()
    } finally {
      setBusy(false)
    }
  }

  const data = queue.data
  if (!data) return null

  const me = session.viewer
  const myEntry = user ? [...data.waiting, ...data.resting, ...data.notCheckedIn].find((entry) => entry.user.id === user.id) : undefined
  const myPosition = user ? data.waiting.findIndex((entry) => entry.user.id === user.id) : -1
  const onCourt = user ? data.courts.find((court) => court.match?.players.some((player) => player.user.id === user.id)) : undefined
  const freeCourt = data.courts.some((court) => !court.match)
  const canCall = data.canManage && live && freeCourt && data.waiting.length >= data.playersPerMatch
  const finished = (results.data ?? []).filter((match) => match.status === 'completed')

  return (
    <section className="queue-panel">
      <div className="section-heading">
        <div>
          <span className="eyebrow">{live ? 'LIVE QUEUE' : 'QUEUE'}</span>
          <h2>{live ? 'On court now' : 'Queue opens when the host starts'}</h2>
        </div>
        {data.canManage && live && (
          <button className="button button-lime" disabled={busy || !canCall} onClick={() => run(() => api.callNextMatch(session.id), 'Next match called.')}>
            <Play size={16} /> Call next match
          </button>
        )}
      </div>
      <p className="form-hint">
        {MODE_LABEL[data.mode]} · {data.playersPerMatch} players per match · {plural(data.courts.length, 'court')}
      </p>

      {live && me.status === 'confirmed' && (
        <div className="queue-me">
          {onCourt ? (
            <strong>You’re playing on {onCourt.label}.</strong>
          ) : !me.checkedIn && !myEntry?.checkedIn ? (
            <>
              <strong>Check in when you arrive to join the queue.</strong>
              <button className="button button-primary" disabled={busy} onClick={() => run(() => api.checkIn(session.id), 'You’re checked in.').then(onSessionChanged)}>
                <UserCheck size={16} /> Check in
              </button>
            </>
          ) : myPosition >= 0 ? (
            <>
              <strong>{myPosition < data.playersPerMatch ? 'You’re up next!' : `You’re #${myPosition + 1} in the queue.`}</strong>
              <button className="button button-ghost" disabled={busy} onClick={() => run(() => api.setQueueState(session.id, 'idle'))}>
                <Coffee size={16} /> Take a break
              </button>
            </>
          ) : (
            <>
              <strong>You’re resting.</strong>
              <button className="button button-primary" disabled={busy} onClick={() => run(() => api.setQueueState(session.id, 'waiting'))}>
                <ListOrdered size={16} /> Rejoin the queue
              </button>
            </>
          )}
        </div>
      )}

      {live && (
        <div className="court-grid">
          {data.courts.map((court) => {
            const match = court.match
            const mayScore = match && user && (data.canManage || match.players.some((player) => player.user.id === user.id))
            return (
              <article key={court.number} className={`court-card ${match ? 'busy' : ''}`}>
                <header>
                  <strong>{court.label}</strong>
                  <span>{match ? 'In play' : 'Free'}</span>
                </header>
                {match ? (
                  <>
                    <div className="court-sides">
                      <p>{sideNames(match, 1)}</p>
                      <i>vs</i>
                      <p>{sideNames(match, 2)}</p>
                    </div>
                    {mayScore && (
                      <button className="button button-primary button-small button-block" onClick={() => setScoring(match)}>
                        Record score
                      </button>
                    )}
                  </>
                ) : (
                  <p className="form-hint">Waiting for the next {data.playersPerMatch} players.</p>
                )}
              </article>
            )
          })}
        </div>
      )}

      {live && (
        <div className="queue-columns">
          <div>
            <h3>Waiting · {data.waiting.length}</h3>
            {data.waiting.length === 0 && <p className="form-hint">Nobody is waiting.</p>}
            <ol className="queue-list">
              {data.waiting.map((entry, index) => (
                <li key={entry.id} className={`${entry.user.id === user?.id ? 'me' : ''} ${index < data.playersPerMatch ? 'next' : ''}`}>
                  <span className="queue-rank">{index + 1}</span>
                  <Avatar user={entry.user} size={30} />
                  <span className="queue-name">{entry.user.displayName}</span>
                  <small>{plural(entry.gamesPlayed, 'game')}</small>
                </li>
              ))}
            </ol>
          </div>
          <div>
            {data.resting.length > 0 && (
              <>
                <h3>Resting · {data.resting.length}</h3>
                <ul className="queue-list">
                  {data.resting.map((entry) => (
                    <li key={entry.id}>
                      <Avatar user={entry.user} size={30} />
                      <span className="queue-name">{entry.user.displayName}</span>
                      <small>{plural(entry.gamesPlayed, 'game')}</small>
                    </li>
                  ))}
                </ul>
              </>
            )}
            {data.notCheckedIn.length > 0 && (
              <>
                <h3>Not here yet · {data.notCheckedIn.length}</h3>
                <ul className="queue-list">
                  {data.notCheckedIn.map((entry) => (
                    <li key={entry.id}>
                      <Avatar user={entry.user} size={30} />
                      <span className="queue-name">{entry.user.displayName}</span>
                      {data.canManage && (
                        <button
                          className="button button-ghost button-small"
                          disabled={busy}
                          onClick={() => run(() => api.participantAction(session.id, entry.id, 'check-in'), `${entry.user.displayName} checked in.`)}
                        >
                          Check in
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        </div>
      )}

      {finished.length > 0 && (
        <div className="results-list">
          <h3>
            <Trophy size={16} /> Results · {finished.length}
          </h3>
          {finished.map((match) => (
            <div key={match.id} className="result-row">
              <span className={match.winnerSide === 1 ? 'winner' : ''}>{sideNames(match, 1)}</span>
              <b>{scoreLine(match)}</b>
              <span className={match.winnerSide === 2 ? 'winner' : ''}>{sideNames(match, 2)}</span>
            </div>
          ))}
        </div>
      )}

      {scoring && sport && (
        <ScoreDialog
          match={scoring}
          sport={sport}
          canVoid={data.canManage}
          onClose={() => setScoring(null)}
          onDone={(message) => {
            setScoring(null)
            notify(message)
            queue.reload()
            results.reload()
          }}
        />
      )}
    </section>
  )
}

interface ScoreDialogProps {
  match: Match
  sport: Sport
  canVoid: boolean
  onClose: () => void
  onDone: (message: string) => void
}

/** Score entry shaped by the sport's scoring rules: games, a single total per side, or just the result. */
function ScoreDialog({ match, sport, canVoid, onClose, onDone }: ScoreDialogProps) {
  const rules = sport.scoringConfig
  const maxGames = rules.bestOf ?? 5
  const [games, setGames] = useState<Array<[string, string]>>([['', '']])
  const [totals, setTotals] = useState<[string, string]>(['', ''])
  const [winner, setWinner] = useState<'1' | '2' | 'draw' | ''>('')
  const [stats, setStats] = useState<Record<string, Record<string, string>>>({})
  const [showStats, setShowStats] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const unit = rules.unit || 'score'
  const gameLabel = (rules.gameLabel || 'Games').replace(/s$/, '')

  function setGame(index: number, side: 0 | 1, value: string) {
    setGames((current) => current.map((game, position) => (position === index ? (side === 0 ? [value, game[1]] : [game[0], value]) : game)))
  }

  function buildResult(): MatchResult | null {
    const result: MatchResult = {}
    if (rules.kind === 'games') {
      const filled = games.filter(([first, second]) => first !== '' && second !== '')
      if (!filled.length) return null
      result.games = filled.map(([first, second]) => [Number(first), Number(second)])
    } else if (rules.kind === 'total') {
      if (totals[0] === '' || totals[1] === '') return null
      result.totals = [Number(totals[0]), Number(totals[1])]
    } else {
      if (!winner) return null
      if (winner === 'draw') result.draw = true
      else result.winner = winner === '1' ? 1 : 2
    }
    const lines: Record<string, Record<string, number>> = {}
    for (const [userId, fields] of Object.entries(stats)) {
      const numbers = Object.fromEntries(Object.entries(fields).filter(([, value]) => value !== '').map(([key, value]) => [key, Number(value)]))
      if (Object.keys(numbers).length) lines[userId] = numbers
    }
    if (Object.keys(lines).length) result.playerStats = lines
    return result
  }

  async function submit() {
    const result = buildResult()
    if (!result) {
      setError('Enter the result first.')
      return
    }
    setBusy(true)
    setError('')
    try {
      await api.recordResult(match.id, result)
      onDone('Result recorded.')
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'Could not save the result.')
    } finally {
      setBusy(false)
    }
  }

  async function voidMatch() {
    setBusy(true)
    try {
      await api.voidMatch(match.id)
      onDone('Match voided. Players are back at the front of the queue.')
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'Could not void the match.')
      setBusy(false)
    }
  }

  return (
    <Modal title={`${match.courtLabel} result`} onClose={onClose}>
      <div className="score-sides">
        <strong>{sideNames(match, 1)}</strong>
        <i>vs</i>
        <strong>{sideNames(match, 2)}</strong>
      </div>

      {rules.kind === 'games' && (
        <div className="form">
          {games.map((game, index) => (
            <div className="score-row" key={index}>
              <span>
                {gameLabel} {index + 1}
              </span>
              <input type="number" inputMode="numeric" min={0} max={999} value={game[0]} onChange={(event) => setGame(index, 0, event.target.value)} aria-label={`${gameLabel} ${index + 1}, first side`} />
              <input type="number" inputMode="numeric" min={0} max={999} value={game[1]} onChange={(event) => setGame(index, 1, event.target.value)} aria-label={`${gameLabel} ${index + 1}, second side`} />
            </div>
          ))}
          {games.length < maxGames && (
            <button className="text-button" onClick={() => setGames((current) => [...current, ['', '']])}>
              + Add {gameLabel.toLowerCase()}
            </button>
          )}
        </div>
      )}

      {rules.kind === 'total' && (
        <div className="score-row">
          <span>Final {unit}</span>
          <input type="number" inputMode="numeric" min={0} value={totals[0]} onChange={(event) => setTotals([event.target.value, totals[1]])} aria-label="First side" />
          <input type="number" inputMode="numeric" min={0} value={totals[1]} onChange={(event) => setTotals([totals[0], event.target.value])} aria-label="Second side" />
        </div>
      )}

      {rules.kind === 'result' && (
        <div className="chip-row">
          <button className={`chip ${winner === '1' ? 'active' : ''}`} onClick={() => setWinner('1')}>
            {sideNames(match, 1)} won
          </button>
          <button className={`chip ${winner === '2' ? 'active' : ''}`} onClick={() => setWinner('2')}>
            {sideNames(match, 2)} won
          </button>
          {rules.allowDraw && (
            <button className={`chip ${winner === 'draw' ? 'active' : ''}`} onClick={() => setWinner('draw')}>
              Draw
            </button>
          )}
        </div>
      )}

      {rules.playerFields.length > 0 && (
        <>
          <button className="text-button" onClick={() => setShowStats((value) => !value)}>
            {showStats ? 'Hide player statistics' : `Add player statistics (${rules.playerFields.map((field) => field.label.toLowerCase()).join(', ')})`}
          </button>
          {showStats && (
            <div className="stat-entry">
              {match.players.map((player) => (
                <div key={player.user.id} className="stat-entry-row">
                  <span>{player.user.displayName}</span>
                  {rules.playerFields.map((field) => (
                    <input
                      key={field.key}
                      type="number"
                      inputMode="numeric"
                      min={0}
                      placeholder={field.label}
                      aria-label={`${player.user.displayName} ${field.label}`}
                      value={stats[player.user.id]?.[field.key] ?? ''}
                      onChange={(event) => setStats((current) => ({ ...current, [player.user.id]: { ...current[player.user.id], [field.key]: event.target.value } }))}
                    />
                  ))}
                </div>
              ))}
              <p className="form-hint">Only fill in numbers that were actually counted. Empty boxes are left out of everyone’s record.</p>
            </div>
          )}
        </>
      )}

      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <div className="button-row">
        <button className="button button-primary" onClick={submit} disabled={busy}>
          {busy ? 'Saving…' : 'Save result'}
        </button>
        {canVoid && (
          <button className="button button-ghost" onClick={voidMatch} disabled={busy}>
            Void match
          </button>
        )}
      </div>
    </Modal>
  )
}
