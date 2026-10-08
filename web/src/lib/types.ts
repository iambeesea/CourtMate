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

export type ParticipantStatus = 'confirmed' | 'waitlisted' | 'pending'
export type SessionStatus = 'scheduled' | 'live' | 'completed' | 'cancelled'

export interface ViewerState {
  status: ParticipantStatus | null
  isHost: boolean
  waitlistPosition: number | null
  checkedIn: boolean
  queueState: 'idle' | 'waiting' | 'playing' | null
}

export interface Session {
  id: string
  title: string
  description: string
  kind: SessionKind
  kindLabel: string
  sport: SportSummary
  facility: { id: string; name: string; slug: string; isDemo: boolean } | null
  venueName: string
  meetupNote: string
  routeName: string
  routeDistanceKm: number | null
  location: LocationInfo
  latitude: number | null
  longitude: number | null
  distanceKm: number | null
  startAt: string
  endAt: string
  timezone: string
  capacity: number
  minPlayers: number
  joined: number
  waitlist: number
  pending: number
  spotsLeft: number
  skillLevel: string
  teamFormat: string
  teamFormatLabel: string
  genderEligibility: 'open' | 'women' | 'men' | 'mixed'
  feeCentavos: number
  joinPolicy: 'open' | 'approval'
  queueMode: QueueMode
  courtsInPlay: number
  status: SessionStatus
  cancelReason: string
  host: PublicUser
  community: { id: string; name: string } | null
  seriesId: string | null
  hasVenueBooking: boolean
  isDemo: boolean
  players: PublicUser[]
  viewer: ViewerState
}

export interface Participant {
  id: string
  user: PublicUser
  status: ParticipantStatus
  joinedAt: string
  checkedIn: boolean
  queueState: 'idle' | 'waiting' | 'playing'
  gamesPlayed: number
  waitlistPosition: number | null
}

export interface SessionDetail extends Session {
  participants: Participant[]
}

export interface MatchPlayer {
  user: PublicUser
  side: 1 | 2
  stats: Record<string, number>
}

export interface Match {
  id: string
  sport: SportSummary
  sessionId: string | null
  courtLabel: string
  status: 'in_progress' | 'completed' | 'void'
  score: { games?: number[][]; totals?: number[] } | null
  winnerSide: 1 | 2 | null
  isDraw: boolean
  startedAt: string
  completedAt: string | null
  players: MatchPlayer[]
  isDemo: boolean
}

export interface Queue {
  sessionId: string
  mode: QueueMode
  status: SessionStatus
  playersPerMatch: number
  courts: Array<{ number: number; label: string; match: Match | null }>
  waiting: Participant[]
  resting: Participant[]
  notCheckedIn: Participant[]
  canManage: boolean
}

export interface SessionDraft {
  title: string
  description: string
  sportId: string
  kind: SessionKind
  startAt: string
  endAt: string
  capacity: number
  minPlayers: number
  skillLevel: string
  teamFormat: string
  genderEligibility: 'open' | 'women' | 'men' | 'mixed'
  feeCentavos: number
  joinPolicy: 'open' | 'approval'
  queueMode: QueueMode
  courtsInPlay: number
  hostPlays: boolean
  facilityId?: string
  resourceId?: string
  cityCode?: string
  barangayCode?: string
  venueName?: string
  meetupNote: string
  routeName?: string
  routeDistanceKm?: number
  repeatWeeks: number
}

export interface MatchResult {
  games?: number[][]
  totals?: [number, number]
  winner?: 1 | 2
  draw?: boolean
  playerStats?: Record<string, Record<string, number>>
}

export interface Member {
  user: PublicUser
  role: string
  joinedAt: string
}

export interface Community {
  id: string
  name: string
  slug: string
  description: string
  city: Place | null
  region: Place | null
  sports: SportSummary[]
  memberCount: number
  visibility: 'public' | 'private'
  isDemo: boolean
  viewerRole: 'owner' | 'admin' | 'member' | null
}

export interface Team {
  id: string
  name: string
  sport: SportSummary
  community: { id: string; name: string } | null
  city: Place | null
  description: string
  memberCount: number
  captain: PublicUser
  isDemo: boolean
  viewerRole: 'captain' | 'member' | null
}

export interface TeamDetail extends Team {
  members: Member[]
}

export interface CommunityDetail extends Community {
  members: Member[]
  teams: Team[]
}

export interface StatValue {
  key: string
  label: string
  value: number
  display: string
  unit: string
  note: string
}

export type FormResult = 'W' | 'L' | 'D'

export interface PlayerStats {
  sport: SportSummary
  recordType: 'matches' | 'activities' | 'attendance'
  hasData: boolean
  summary: StatValue[]
  recentForm: FormResult[]
  streakType: FormResult | null
  streak: number
  bestWinStreak: number
  byMonth: Array<{ month: string; label: string; count: number }>
  partners: Array<{ user: PublicUser; matches: number; wins: number }>
  containsDemoData: boolean
}

export interface RecordOverview {
  sport: SportSummary
  recordType: 'matches' | 'activities' | 'attendance'
  entries: number
  lastPlayedAt: string | null
}

export interface MyMatch extends Match {
  result: FormResult
  mySide: 1 | 2
}

export interface Activity {
  id: string
  sport: SportSummary
  occurredAt: string
  metrics: Record<string, number>
  source: string
  note: string
  isDemo: boolean
}

export interface Achievement {
  id: string
  label: string
  description: string
}

export interface AppNotification {
  id: string
  kind: string
  title: string
  body: string
  link: string
  readAt: string | null
  createdAt: string
}

export interface NotificationList {
  unread: number
  items: AppNotification[]
}

export interface OperatorFacility extends FacilityDetail {
  contactName: string
  contactEmail: string
  contactPhone: string
  verificationNotes: string
  staff: Array<{ user: PublicUser; role: string }>
  pendingRequests: number
}

export interface AdminFacility extends OperatorFacility {
  owner: PublicUser
  createdAt: string
}

export interface Occupancy {
  facilityId: string
  dateFrom: string
  dateTo: string
  openMinutes: number
  bookedMinutes: number
  blockedMinutes: number
  occupancyPercent: number
  confirmedBookings: number
  pendingBookings: number
  cancelledBookings: number
  bookedValueCentavos: number
  resources: Array<{ resourceId: string; name: string; openMinutes: number; bookedMinutes: number; blockedMinutes: number; occupancyPercent: number }>
}

export interface FacilityDraft {
  name: string
  description: string
  addressLine: string
  cityCode: string
  barangayCode?: string | null
  latitude?: number | null
  longitude?: number | null
  amenities: string[]
  sportIds: string[]
  contactName: string
  contactEmail: string
  contactPhone: string
}

export interface ResourceDraft {
  name: string
  resourceTypeId: string
  sportIds: string[]
  description: string
  capacity: number
  slotMinutes: number
  hourlyRateCentavos: number
  parentId?: string | null
}

export type VerificationStatus = 'pending' | 'verified' | 'rejected' | 'suspended'
