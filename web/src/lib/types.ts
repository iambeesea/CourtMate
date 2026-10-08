// Shapes returned by the CourtMate API (camelCase JSON).

export interface Place {
  code: string
  name: string
}

export interface Region extends Place {
  regionName: string
  islandGroup: string
}

export interface Province extends Place {
  regionCode: string
}

export interface City extends Place {
  regionCode: string
  provinceCode: string | null
  isCity: boolean
}

export interface Barangay extends Place {
  cityCode: string
}

export interface LocationInfo {
  region: Place
  province: Place | null
  city: Place
  barangay: Place | null
}

export interface TeamFormat {
  id: string
  label: string
  playersPerSide: number
}

export interface ActivityField {
  key: string
  label: string
  unit: string
  type: 'number' | 'integer'
  min: number | null
  max: number | null
  required: boolean
}

export interface SportSummary {
  id: string
  name: string
  icon: string
  categoryId: string
}

export type SessionKind =
  | 'open_play'
  | 'pickup_game'
  | 'class'
  | 'sparring'
  | 'group_activity'
  | 'tee_time'
  | 'challenge'
  | 'tournament'
  | 'event'

export type QueueMode = 'none' | 'rotation' | 'winner_stays'

export interface Sport extends SportSummary {
  category: { id: string; name: string }
  description: string
  bookingEligible: boolean
  queueEligible: boolean
  playerConfig: { minPlayers: number; maxPlayers: number; teamFormats: TeamFormat[] }
  matchFormat: {
    type: 'two_sided' | 'individual' | 'class' | 'group'
    sessionKinds: SessionKind[]
    queueModes: Array<'rotation' | 'winner_stays'>
    skillLevels: string[]
    usesRoutes: boolean
    kindLabels: Record<string, string>
  }
  scoringConfig: {
    kind: 'games' | 'total' | 'result' | 'individual' | 'none'
    unit: string
    bestOf: number | null
    gameLabel: string
    allowDraw: boolean
    playerFields: Array<{ key: string; label: string }>
    activityFields: ActivityField[]
  }
  resourceTypes: string[]
  isActive: boolean
}

export interface Category {
  id: string
  name: string
}

export interface PublicUser {
  id: string
  displayName: string
  initials: string
  avatarColor: string
  isDemo: boolean
}

export interface SportProfile {
  sportId: string
  skillLevel: string
  isPrimary: boolean
}

export interface Me extends PublicUser {
  email: string
  role: 'player' | 'admin'
  bio: string
  city: City | null
  sports: SportProfile[]
  managedFacilityIds: string[]
  createdAt: string
}

export interface TokenResponse {
  accessToken: string
  expiresAt: string
  user: Me
}

export interface AppConfig {
  demoLogin: boolean
  demoData: boolean
  defaultTimezone: string
  bookingQuantumMinutes: number
  version: string
}

export interface ResourceInfo {
  id: string
  name: string
  resourceType: { id: string; name: string }
  parentId: string | null
  childIds: string[]
  description: string
  capacity: number
  slotMinutes: number
  hourlyRateCentavos: number
  isActive: boolean
  sportIds: string[]
}

export interface FacilitySummary {
  id: string
  name: string
  slug: string
  description: string
  addressLine: string
  location: LocationInfo
  latitude: number | null
  longitude: number | null
  timezone: string
  amenities: string[]
  photos: Array<{ url: string; caption: string }>
  sports: SportSummary[]
  resourceCount: number
  fromRateCentavos: number | null
  isDemo: boolean
  verificationStatus: string
  distanceKm: number | null
}

export interface OpeningHours {
  weekday: number
  openMinute: number
  closeMinute: number
  openLabel: string
  closeLabel: string
}

export interface BookingRules {
  requiresApproval: boolean
  minNoticeMinutes: number
  maxAdvanceDays: number
  cancellationWindowHours: number
  minBookingMinutes: number
  maxBookingMinutes: number
}

export interface FacilityDetail extends FacilitySummary {
  hours: OpeningHours[]
  resources: ResourceInfo[]
  bookingRules: BookingRules
}

export type SlotStatus = 'available' | 'booked' | 'blocked' | 'past' | 'closed'

export interface Slot {
  startAt: string
  endAt: string
  status: SlotStatus
  priceCentavos: number
}

export interface FacilityAvailability {
  facilityId: string
  date: string
  timezone: string
  isOpen: boolean
  openMinute: number | null
  closeMinute: number | null
  resources: Array<{ resource: ResourceInfo; slots: Slot[] }>
}

export type ReservationStatus = 'pending' | 'confirmed' | 'rejected' | 'cancelled' | 'completed'

export interface Reservation {
  id: string
  kind: 'booking' | 'block'
  status: ReservationStatus
  resource: { id: string; name: string; resourceType: { id: string; name: string } }
  facility: { id: string; name: string; cityName: string; addressLine: string; timezone: string; isDemo: boolean }
  sport: SportSummary | null
  organizer: PublicUser
  startAt: string
  endAt: string
  priceCentavos: number
  paymentStatus: 'not_required' | 'pay_at_venue' | 'paid' | 'refunded'
  partySize: number
  note: string
  freeCancelUntil: string | null
  lateCancellation: boolean
  seriesId: string | null
  createdAt: string
  cancelledAt: string | null
  cancelReason: string
  canCancel: boolean
}

export interface AreaParams {
  regionCode?: string
  provinceCode?: string
  cityCode?: string
  barangayCode?: string
  lat?: number
  lng?: number
  radiusKm?: number
}
