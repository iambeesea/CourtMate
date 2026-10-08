import type {
  AppConfig,
  AreaParams,
  Barangay,
  Category,
  City,
  FacilityAvailability,
  FacilityDetail,
  FacilitySummary,
  Match,
  MatchResult,
  Me,
  Province,
  Queue,
  Region,
  Reservation,
  Session,
  SessionDetail,
  SessionDraft,
  Sport,
  SportProfile,
  TokenResponse,
} from './types'

const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')
const TOKEN_KEY = 'courtmate.token'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }

  /** The API could not be reached at all (offline, or the server is still waking up). */
  get isNetwork() {
    return this.status === 0
  }
}

function readStoredToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

let token: string | null = readStoredToken()
let onSessionExpired: (() => void) | null = null

export function getToken() {
  return token
}

export function setToken(value: string | null) {
  token = value
  try {
    if (value) window.localStorage.setItem(TOKEN_KEY, value)
    else window.localStorage.removeItem(TOKEN_KEY)
  } catch {
    // Storage can be unavailable (private mode); the token then lives for this tab only.
  }
}

export function handleSessionExpired(callback: (() => void) | null) {
  onSessionExpired = callback
}

type Query = Record<string, string | number | boolean | null | undefined>

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  query?: Query
  body?: unknown
  signal?: AbortSignal
}

function describe(detail: unknown, status: number): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0] as { msg?: string; loc?: Array<string | number> }
    const field = first.loc?.filter((part) => part !== 'body' && part !== 'query').join(' ')
    return field ? `${field}: ${first.msg ?? 'is not valid'}` : (first.msg ?? 'Some details are not valid.')
  }
  if (status === 429) return 'Too many attempts. Please wait a moment and try again.'
  return status >= 500 ? 'Something went wrong on our side. Please try again.' : 'That request could not be completed.'
}

export async function request<T>(path: string, { method = 'GET', query, body, signal }: RequestOptions = {}): Promise<T> {
  const url = new URL(`${API_URL}${path}`)
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, String(value))
  }
  const sentToken = token
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (sentToken) headers.Authorization = `Bearer ${sentToken}`

  let response: Response
  try {
    response = await fetch(url, { method, headers, body: body === undefined ? undefined : JSON.stringify(body), signal })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'CourtMate can’t be reached right now. Check your connection and try again.')
  }

  if (response.status === 204) return undefined as T
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    if (response.status === 401 && sentToken && sentToken === token) onSessionExpired?.()
    throw new ApiError(response.status, describe(payload?.detail, response.status))
  }
  return payload as T
}

const v1 = (path: string) => `/api/v1${path}`

export interface FacilityQuery extends AreaParams {
  sportId?: string
  resourceType?: string
  q?: string
  limit?: number
}

export interface SessionQuery extends AreaParams {
  sportId?: string
  category?: string
  kind?: string
  facilityId?: string
  communityId?: string
  startsAfter?: string
  startsBefore?: string
  skillLevel?: string
  free?: boolean
  hasSpots?: boolean
  q?: string
  limit?: number
}

export interface BookingRequest {
  resourceId: string
  startAt: string
  endAt: string
  sportId?: string
  partySize: number
  note: string
  repeatWeeks: number
}

export interface ProfileUpdate {
  displayName?: string
  bio?: string
  cityCode?: string | null
  sports?: SportProfile[]
}

export const api = {
  config: () => request<AppConfig>(v1('/config')),

  register: (email: string, password: string, displayName: string) =>
    request<TokenResponse>(v1('/auth/register'), { method: 'POST', body: { email, password, displayName } }),
  login: (email: string, password: string) => request<TokenResponse>(v1('/auth/login'), { method: 'POST', body: { email, password } }),
  demoLogin: (persona: 'player' | 'operator' | 'admin') => request<TokenResponse>(v1('/auth/demo'), { method: 'POST', body: { persona } }),
  logout: () => request<void>(v1('/auth/logout'), { method: 'POST' }),
  me: () => request<Me>(v1('/auth/me')),
  updateMe: (changes: ProfileUpdate) => request<Me>(v1('/auth/me'), { method: 'PATCH', body: changes }),

  sports: () => request<Sport[]>(v1('/sports')),
  categories: () => request<Category[]>(v1('/sports/categories')),

  regions: () => request<Region[]>(v1('/geo/regions')),
  provinces: (regionCode: string) => request<Province[]>(v1('/geo/provinces'), { query: { regionCode } }),
  cities: (query: { regionCode?: string; provinceCode?: string; q?: string }) =>
    request<City[]>(v1('/geo/cities'), { query: { ...query, limit: 2000 } }),
  barangays: (cityCode: string) => request<Barangay[]>(v1('/geo/barangays'), { query: { cityCode } }),

  facilities: (query: FacilityQuery, signal?: AbortSignal) => request<FacilitySummary[]>(v1('/facilities'), { query: { ...query }, signal }),
  facility: (id: string) => request<FacilityDetail>(v1(`/facilities/${encodeURIComponent(id)}`)),
  availability: (id: string, date: string, sportId?: string) =>
    request<FacilityAvailability>(v1(`/facilities/${encodeURIComponent(id)}/availability`), { query: { date, sportId } }),

  reservations: (scope: 'upcoming' | 'past' | 'all') => request<Reservation[]>(v1('/reservations'), { query: { scope } }),
  book: (payload: BookingRequest) => request<Reservation[]>(v1('/reservations'), { method: 'POST', body: payload }),
  cancelReservation: (id: string, reason: string) =>
    request<Reservation>(v1(`/reservations/${id}/cancel`), { method: 'POST', body: { reason } }),

  sessions: (query: SessionQuery, signal?: AbortSignal) => request<Session[]>(v1('/sessions'), { query: { ...query }, signal }),
  mySessions: (role: 'playing' | 'hosting', scope: 'upcoming' | 'past') => request<Session[]>(v1('/sessions/mine'), { query: { role, scope } }),
  session: (id: string) => request<SessionDetail>(v1(`/sessions/${id}`)),
  createSession: (draft: SessionDraft) => request<Session[]>(v1('/sessions'), { method: 'POST', body: draft }),
  updateSession: (id: string, changes: Partial<SessionDraft>) => request<SessionDetail>(v1(`/sessions/${id}`), { method: 'PATCH', body: changes }),
  joinSession: (id: string) => request<SessionDetail>(v1(`/sessions/${id}/join`), { method: 'POST' }),
  leaveSession: (id: string) => request<SessionDetail>(v1(`/sessions/${id}/leave`), { method: 'POST' }),
  sessionAction: (id: string, action: 'start' | 'complete' | 'cancel', reason = '') =>
    request<SessionDetail>(v1(`/sessions/${id}/${action}`), { method: 'POST', body: action === 'cancel' ? { reason } : undefined }),
  participantAction: (id: string, participantId: string, action: 'approve' | 'decline' | 'remove' | 'check-in') =>
    request<SessionDetail>(v1(`/sessions/${id}/participants/${participantId}/${action}`), { method: 'POST' }),

  queue: (id: string, signal?: AbortSignal) => request<Queue>(v1(`/sessions/${id}/queue`), { signal }),
  checkIn: (id: string) => request<Queue>(v1(`/sessions/${id}/check-in`), { method: 'POST' }),
  setQueueState: (id: string, state: 'waiting' | 'idle') => request<Queue>(v1(`/sessions/${id}/queue/me`), { method: 'POST', body: { state } }),
  callNextMatch: (id: string) => request<Queue>(v1(`/sessions/${id}/queue/next`), { method: 'POST', body: {} }),
  sessionMatches: (id: string) => request<Match[]>(v1(`/sessions/${id}/matches`)),
  recordResult: (matchId: string, result: MatchResult) => request<Match>(v1(`/matches/${matchId}/result`), { method: 'POST', body: result }),
  voidMatch: (matchId: string) => request<Match>(v1(`/matches/${matchId}/void`), { method: 'POST' }),
}
