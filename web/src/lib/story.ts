import type { PlayerStats } from './types'

/** What goes on the 1080 × 1920 share card. */
export interface StoryData {
  title: [string, string]
  headline: string
  headlineLabel: string
  lines: string[]
  footer: string
  /** Demo figures are marked on the card so they are never mistaken for real results. */
  demo: boolean
}

function line(display: string, unit: string, label: string): string {
  return [display + (unit === '%' ? '%' : ''), unit && unit !== '%' ? unit : '', label].filter(Boolean).join(' ').toUpperCase()
}

export function storyFromStats(stats: PlayerStats, playerName: string, skillLevel: string): StoryData {
  const find = (key: string) => stats.summary.find((item) => item.key === key)
  const footer = [playerName, [stats.sport.name, skillLevel].filter(Boolean).join(' ')].join('  ·  ').toUpperCase()

  if (stats.recordType === 'matches') {
    const wins = find('wins')
    const lines = [`${find('win_rate')?.display ?? '0%'} WIN RATE`]
    lines.push(stats.streakType === 'W' && stats.streak > 1 ? `${stats.streak} GAME STREAK` : `${find('matches')?.display ?? '0'} MATCHES PLAYED`)
    return { title: ['MATCH', 'RECAP'], headline: wins?.display ?? '0', headlineLabel: 'WINS RECORDED', lines, footer, demo: stats.containsDemoData }
  }

  // Activities and attendance: lead with the most meaningful figure, then the next two.
  const [first, ...rest] = stats.summary
  const lead = stats.recordType === 'activities' ? (rest.find((item) => item.unit) ?? first) : first
  const others = stats.summary.filter((item) => item !== lead).slice(0, 2)
  return {
    title: [stats.sport.name.split(' ')[0].toUpperCase(), stats.recordType === 'activities' ? 'LOG' : 'RECORD'],
    headline: lead?.display ?? '0',
    headlineLabel: [lead?.unit, lead?.label].filter(Boolean).join(' ').toUpperCase(),
    lines: others.map((item) => line(item.display, item.unit, item.label)),
    footer,
    demo: stats.containsDemoData,
  }
}

/** Draw the Instagram Story card. Returns null where canvas is unavailable. */
export function renderStory(data: StoryData): HTMLCanvasElement | null {
  const canvas = document.createElement('canvas')
  canvas.width = 1080
  canvas.height = 1920
  const context = canvas.getContext('2d')
  if (!context) return null

  context.fillStyle = '#1f3b73'
  context.fillRect(0, 0, 1080, 1920)
  context.fillStyle = '#e0fe2c'
  context.beginPath()
  context.arc(900, 250, 310, 0, Math.PI * 2)
  context.fill()

  context.fillStyle = '#ffffff'
  context.font = '700 52px Arial'
  context.fillText('COURTMATE', 90, 130)
  context.font = '700 98px Arial'
  context.fillText(data.title[0], 90, 450)
  context.fillText(data.title[1], 90, 555)

  context.fillStyle = '#e0fe2c'
  // Long figures (a pace, a distance) shrink to stay inside the card.
  let size = 210
  do {
    context.font = `700 ${size}px Arial`
    size -= 10
  } while (context.measureText(data.headline).width > 880 && size > 90)
  context.fillText(data.headline, 90, 900)
  context.fillStyle = '#ffffff'
  context.font = '600 44px Arial'
  context.fillText(data.headlineLabel, 100, 970)

  if (data.lines.length) {
    context.fillStyle = 'rgba(255,255,255,.18)'
    context.fillRect(90, 1120, 900, 130 + data.lines.length * 115)
    context.fillStyle = '#ffffff'
    context.font = '700 56px Arial'
    data.lines.forEach((text, index) => context.fillText(text, 150, 1250 + index * 110, 780))
  }

  context.fillStyle = '#e0fe2c'
  context.font = '700 42px Arial'
  context.fillText(data.footer, 90, 1720, 900)
  context.fillStyle = '#ffffff'
  context.font = '400 32px Arial'
  context.fillText(data.demo ? 'Demo data · Made to play. Built to connect.' : 'Made to play. Built to connect.', 90, 1790)
  return canvas
}
