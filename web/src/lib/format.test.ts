import { describe, expect, it } from 'vitest'
import {
  addDays,
  dateKey,
  dayParts,
  durationLabel,
  formatDistance,
  formatTime,
  formatTimeRange,
  keyParts,
  minutesBetween,
  peso,
  placeLine,
  plural,
  priceLabel,
  relativeDayLabel,
  weekdayOf,
} from './format'

describe('Philippine time formatting', () => {
  // 16:30 UTC on 8 October is 00:30 on 9 October in Manila.
  const lateUtc = '2026-10-08T16:30:00Z'

  it('shows Manila wall-clock time regardless of the device time zone', () => {
    expect(formatTime('2026-10-08T02:00:00Z')).toBe('10:00 AM')
    expect(formatTime(lateUtc)).toBe('12:30 AM')
    expect(formatTimeRange('2026-10-08T10:30:00Z', '2026-10-08T13:00:00Z')).toBe('6:30 PM – 9:00 PM')
  })

  it('puts a late-evening UTC instant on the next Manila calendar day', () => {
    expect(dateKey(lateUtc)).toBe('2026-10-09')
    expect(dayParts(lateUtc)).toEqual({ weekday: 'FRI', day: '9', month: 'OCT', year: '2026' })
  })

  it('does calendar arithmetic on day keys', () => {
    expect(addDays('2026-10-31', 1)).toBe('2026-11-01')
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01')
    expect(addDays('2026-03-01', -1)).toBe('2026-02-28')
    expect(keyParts('2026-10-08')).toMatchObject({ weekday: 'THU', day: '8', month: 'OCT' })
  })

  it('numbers weekdays from Monday, like the API', () => {
    expect(weekdayOf('2026-10-05')).toBe(0)
    expect(weekdayOf('2026-10-08')).toBe(3)
    expect(weekdayOf('2026-10-11')).toBe(6)
  })

  it('labels today and tomorrow', () => {
    expect(relativeDayLabel('2026-10-08', '2026-10-08')).toBe('Today')
    expect(relativeDayLabel('2026-10-09', '2026-10-08')).toBe('Tomorrow')
    expect(relativeDayLabel('2026-10-12', '2026-10-08')).toBe('Mon, Oct 12')
  })
})

describe('money, distance and duration', () => {
  it('formats centavos as pesos', () => {
    expect(peso(40000)).toBe('₱400')
    expect(peso(123456)).toBe('₱1,234.56')
    expect(priceLabel(0)).toBe('Free')
  })

  it('formats distances', () => {
    expect(formatDistance(null)).toBe('')
    expect(formatDistance(0.42)).toBe('400 m away')
    expect(formatDistance(3.26)).toBe('3.3 km away')
    expect(formatDistance(28.4)).toBe('28 km away')
  })

  it('formats durations', () => {
    expect(durationLabel(30)).toBe('30 min')
    expect(durationLabel(60)).toBe('1 hr')
    expect(durationLabel(150)).toBe('2 hr 30 min')
    expect(minutesBetween('2026-10-08T02:00:00Z', '2026-10-08T04:00:00Z')).toBe(120)
  })

  it('pluralises and describes places', () => {
    expect(plural(1, 'venue')).toBe('1 venue')
    expect(plural(3, 'venue')).toBe('3 venues')
    expect(placeLine({ barangay: { name: 'Bulihan' }, city: { name: 'City of Malolos' }, province: { name: 'Bulacan' } })).toBe('Bulihan, City of Malolos, Bulacan')
    expect(placeLine({ barangay: null, city: { name: 'Quezon City' }, province: null })).toBe('Quezon City')
  })
})
