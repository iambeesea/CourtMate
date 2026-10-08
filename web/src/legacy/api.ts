import { demoStats } from './data'
import type { PlayerStats } from './types'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export async function getPlayerStats(): Promise<PlayerStats> {
  try {
    const response = await fetch(`${API_URL}/api/v1/players/me/stats`)
    if (!response.ok) throw new Error(`Request failed: ${response.status}`)
    return (await response.json()) as PlayerStats
  } catch {
    return demoStats
  }
}
