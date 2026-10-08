import { demoSessions, demoStats } from './data'
import type { PlayerStats, Session } from './types'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.json() as Promise<T>
}

export async function getSessions(): Promise<Session[]> {
  try { return await request<Session[]>('/api/v1/sessions') } catch { return demoSessions }
}

export async function getPlayerStats(): Promise<PlayerStats> {
  try { return await request<PlayerStats>('/api/v1/players/me/stats') } catch { return demoStats }
}

export async function joinSession(id: string): Promise<Session | null> {
  try { return await request<Session>(`/api/v1/sessions/${id}/join`, { method: 'POST' }) } catch { return null }
}

export async function leaveSession(id: string): Promise<Session | null> {
  try { return await request<Session>(`/api/v1/sessions/${id}/leave`, { method: 'POST' }) } catch { return null }
}
