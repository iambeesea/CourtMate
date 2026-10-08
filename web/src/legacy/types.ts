export interface PlayerStats {
  matches: number
  wins: number
  losses: number
  winRate: number
  streak: number
  rating: number
  recentForm: Array<'W' | 'L'>
}
