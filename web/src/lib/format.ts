// CourtMate schedules are shown in Philippine time no matter where the device is.
export const TIME_ZONE = 'Asia/Manila'
const LOCALE = 'en-PH'

const pesoFormat = new Intl.NumberFormat(LOCALE, { style: 'currency', currency: 'PHP', maximumFractionDigits: 0 })
const pesoCentsFormat = new Intl.NumberFormat(LOCALE, { style: 'currency', currency: 'PHP', minimumFractionDigits: 2 })
const timeFormat = new Intl.DateTimeFormat(LOCALE, { timeZone: TIME_ZONE, hour: 'numeric', minute: '2-digit', hour12: true })
const partsFormat = new Intl.DateTimeFormat('en-US', {
  timeZone: TIME_ZONE,
  weekday: 'short',
  month: 'short',
  day: 'numeric',
  year: 'numeric',
})
const longDateFormat = new Intl.DateTimeFormat('en-US', { timeZone: TIME_ZONE, weekday: 'long', month: 'long', day: 'numeric' })
const mediumDateFormat = new Intl.DateTimeFormat('en-US', { timeZone: TIME_ZONE, weekday: 'short', month: 'short', day: 'numeric' })
const keyFormat = new Intl.DateTimeFormat('en-CA', { timeZone: TIME_ZONE, year: 'numeric', month: '2-digit', day: '2-digit' })

export function peso(centavos: number): string {
  return centavos % 100 === 0 ? pesoFormat.format(centavos / 100) : pesoCentsFormat.format(centavos / 100)
}

export function priceLabel(centavos: number): string {
  return centavos === 0 ? 'Free' : peso(centavos)
}

function clock(value: string | Date): string {
  return timeFormat.format(typeof value === 'string' ? new Date(value) : value).replace(/ | /g, ' ').toUpperCase()
}

export function formatTime(iso: string): string {
  return clock(iso)
}

export function formatTimeRange(startIso: string, endIso: string): string {
  return `${clock(startIso)} – ${clock(endIso)}`
}

export interface DayParts {
  weekday: string
  day: string
  month: string
  year: string
}

export function dayParts(value: string | Date): DayParts {
  const parts = partsFormat.formatToParts(typeof value === 'string' ? new Date(value) : value)
  const pick = (type: string) => parts.find((part) => part.type === type)?.value ?? ''
  return { weekday: pick('weekday').toUpperCase(), day: pick('day'), month: pick('month').toUpperCase(), year: pick('year') }
}

export function formatLongDate(value: string | Date): string {
  return longDateFormat.format(typeof value === 'string' ? new Date(value) : value)
}

export function formatMediumDate(value: string | Date): string {
  return mediumDateFormat.format(typeof value === 'string' ? new Date(value) : value)
}

/** Calendar day in Manila as YYYY-MM-DD. */
export function dateKey(value: string | Date = new Date()): string {
  return keyFormat.format(typeof value === 'string' ? new Date(value) : value)
}

function keyToUtcNoon(key: string): Date {
  const [year, month, day] = key.split('-').map(Number)
  return new Date(Date.UTC(year, month - 1, day, 12))
}

export function addDays(key: string, days: number): string {
  const date = keyToUtcNoon(key)
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}

/** 0 = Monday … 6 = Sunday, matching the API's opening-hours weekday. */
export function weekdayOf(key: string): number {
  return (keyToUtcNoon(key).getUTCDay() + 6) % 7
}

export function keyParts(key: string): DayParts {
  // Noon UTC is the same calendar day in Manila.
  return dayParts(keyToUtcNoon(key))
}

export function relativeDayLabel(key: string, today: string = dateKey()): string {
  if (key === today) return 'Today'
  if (key === addDays(today, 1)) return 'Tomorrow'
  return formatMediumDate(keyToUtcNoon(key))
}

export function formatDistance(km: number | null | undefined): string {
  if (km === null || km === undefined) return ''
  if (km < 1) return `${Math.max(50, Math.round((km * 1000) / 50) * 50)} m away`
  return `${km < 10 ? km.toFixed(1) : Math.round(km)} km away`
}

export function durationLabel(minutes: number): string {
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return rest ? `${hours} hr ${rest} min` : `${hours} hr`
}

export function minutesBetween(startIso: string, endIso: string): number {
  return Math.round((new Date(endIso).getTime() - new Date(startIso).getTime()) / 60000)
}

export const WEEKDAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

export function plural(count: number, singular: string, pluralForm = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : pluralForm}`
}

export function placeLine(location: { barangay: { name: string } | null; city: { name: string }; province: { name: string } | null }): string {
  return [location.barangay?.name, location.city.name, location.province?.name].filter(Boolean).join(', ')
}
