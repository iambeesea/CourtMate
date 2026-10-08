import { describe, expect, it } from 'vitest'
import { joinState, joinedMessage, scoreLine, spotsLabel } from './sessionText'
import { storyFromStats } from './story'
import type { Match, PlayerStats, Session } from './types'

function session(overrides: Partial<Session> = {}, viewer: Partial<Session['viewer']> = {}): Session {
  return {
    status: 'scheduled',
    joinPolicy: 'open',
    spotsLeft: 3,
    waitlist: 0,
    ...overrides,
    viewer: { status: null, isHost: false, waitlistPosition: null, checkedIn: false, queueState: null, ...viewer },
  } as Session
}

describe('join button wording', () => {
  it('offers the right action for someone who has not joined', () => {
    expect(joinState(session())).toEqual({ label: 'Join', action: 'join', joined: false })
    expect(joinState(session({ spotsLeft: 0 })).label).toBe('Join waitlist')
    expect(joinState(session({ joinPolicy: 'approval' })).label).toBe('Request to join')
  })

  it('reflects where the player stands', () => {
    expect(joinState(session({}, { status: 'confirmed' }))).toMatchObject({ label: 'Joined', action: 'view', joined: true })
    expect(joinState(session({}, { status: 'waitlisted', waitlistPosition: 2 })).label).toBe('On the waitlist · #2')
    expect(joinState(session({}, { status: 'pending' })).label).toBe('Waiting for the host')
    expect(joinState(session({}, { isHost: true })).label).toBe('Manage session')
  })

  it('never offers to join a session that is over', () => {
    expect(joinState(session({ status: 'cancelled' })).action).toBe('view')
    expect(joinState(session({ status: 'completed' })).label).toBe('Finished')
  })

  it('confirms what happened after joining', () => {
    expect(joinedMessage(session({}, { status: 'confirmed' }))).toBe('Your spot is confirmed!')
    expect(joinedMessage(session({}, { status: 'waitlisted', waitlistPosition: 4 }))).toContain('#4')
    expect(joinedMessage(session({}, { status: 'pending' }))).toBe('Request sent to the host.')
  })

  it('summarises places', () => {
    expect(spotsLabel(session({ spotsLeft: 1 }))).toBe('1 spot left')
    expect(spotsLabel(session({ spotsLeft: 0, waitlist: 3 }))).toBe('Full · 3 waiting')
    expect(spotsLabel(session({ spotsLeft: 0 }))).toBe('Full')
  })
})

describe('scores', () => {
  it('prints games, totals and draws', () => {
    expect(scoreLine({ score: { games: [[21, 15], [18, 21], [21, 19]], totals: [2, 1] }, isDraw: false } as Match)).toBe('21–15, 18–21, 21–19')
    expect(scoreLine({ score: { totals: [78, 70] }, isDraw: false } as Match)).toBe('78–70')
    expect(scoreLine({ score: {}, isDraw: true } as Match)).toBe('Draw')
  })
})

describe('story card content', () => {
  const sport = { id: 'pickleball', name: 'Pickleball', icon: '', categoryId: 'racket_paddle' }
  const stat = (key: string, label: string, display: string, unit = '') => ({ key, label, value: Number.parseFloat(display), display, unit, note: '' })

  it('leads a match record with wins and marks demo figures', () => {
    const stats = {
      sport,
      recordType: 'matches',
      summary: [stat('matches', 'Matches played', '28'), stat('wins', 'Wins', '18'), stat('win_rate', 'Win rate', '64%', '%')],
      streakType: 'W',
      streak: 4,
      containsDemoData: true,
    } as PlayerStats
    expect(storyFromStats(stats, 'Demo Player', '3.0')).toEqual({
      title: ['MATCH', 'RECAP'],
      headline: '18',
      headlineLabel: 'WINS RECORDED',
      lines: ['64% WIN RATE', '4 GAME STREAK'],
      footer: 'DEMO PLAYER  ·  PICKLEBALL 3.0',
      demo: true,
    })
  })

  it('leads an activity record with its main measurement', () => {
    const stats = {
      sport: { ...sport, id: 'running', name: 'Running' },
      recordType: 'activities',
      summary: [stat('activities', 'Runs logged', '5'), stat('distance', 'Total distance', '50.7', 'km'), stat('pace', 'Average pace', '6:04', 'min/km')],
      streakType: null,
      streak: 0,
      containsDemoData: false,
    } as PlayerStats
    const story = storyFromStats(stats, 'Ana Reyes', '')
    expect(story.title).toEqual(['RUNNING', 'LOG'])
    expect(story.headline).toBe('50.7')
    expect(story.headlineLabel).toBe('KM TOTAL DISTANCE')
    expect(story.lines).toEqual(['5 RUNS LOGGED', '6:04 MIN/KM AVERAGE PACE'])
    expect(story.demo).toBe(false)
  })
})
