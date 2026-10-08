export type Sport = 'Pickleball' | 'Badminton'

export interface Player {
  id: string
  name: string
  initials: string
  level: string
  color: string
}

export interface Session {
  id: string
  title: string
  sport: Sport
  venue: string
  city: string
  date: string
  dayLabel: string
  time: string
  level: string
  format: string
  price: number
  capacity: number
  joined: number
  waitlist: number
  organizer: string
  accent: 'lime' | 'violet' | 'orange'
  players: Player[]
  isJoined?: boolean
}

export interface PlayerStats {
  matches: number
  wins: number
  losses: number
  winRate: number
  streak: number
  rating: number
  recentForm: Array<'W' | 'L'>
}
