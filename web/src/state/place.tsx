import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import type { AreaParams, Place } from '../lib/types'

/** Where the visitor is looking: everywhere, an administrative area, or a radius around a point. */
export type PlaceFilter =
  | { mode: 'all' }
  | { mode: 'area'; region: Place; province?: Place; city?: Place; barangay?: Place }
  | { mode: 'nearby'; lat: number; lng: number; radiusKm: number }

const STORAGE_KEY = 'courtmate.place'

function load(): PlaceFilter {
  try {
    const saved = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? 'null') as PlaceFilter | null
    if (saved && (saved.mode === 'all' || saved.mode === 'area' || saved.mode === 'nearby')) return saved
  } catch {
    // Ignore unreadable storage.
  }
  return { mode: 'all' }
}

// eslint-disable-next-line react-refresh/only-export-components
export function placeLabel(filter: PlaceFilter): string {
  if (filter.mode === 'nearby') return `Within ${filter.radiusKm} km of you`
  if (filter.mode === 'area') {
    const narrowest = filter.city ?? filter.province ?? filter.region
    return filter.barangay ? `${filter.barangay.name}, ${narrowest.name}` : narrowest.name
  }
  return 'All Philippines'
}

// eslint-disable-next-line react-refresh/only-export-components
export function placeParams(filter: PlaceFilter): AreaParams {
  if (filter.mode === 'nearby') return { lat: filter.lat, lng: filter.lng, radiusKm: filter.radiusKm }
  if (filter.mode === 'area') {
    return {
      regionCode: filter.region.code,
      provinceCode: filter.province?.code,
      cityCode: filter.city?.code,
      barangayCode: filter.barangay?.code,
    }
  }
  return {}
}

interface PlaceContextValue {
  place: PlaceFilter
  setPlace: (filter: PlaceFilter) => void
  pickerOpen: boolean
  openPicker: () => void
  closePicker: () => void
}

const PlaceContext = createContext<PlaceContextValue | null>(null)

export function PlaceProvider({ children }: { children: ReactNode }) {
  const [place, setPlaceState] = useState<PlaceFilter>(load)
  const [pickerOpen, setPickerOpen] = useState(false)

  const setPlace = useCallback((filter: PlaceFilter) => {
    setPlaceState(filter)
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(filter))
    } catch {
      // The choice still applies for this visit.
    }
  }, [])

  const value = useMemo(
    () => ({ place, setPlace, pickerOpen, openPicker: () => setPickerOpen(true), closePicker: () => setPickerOpen(false) }),
    [place, setPlace, pickerOpen],
  )
  return <PlaceContext.Provider value={value}>{children}</PlaceContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function usePlace(): PlaceContextValue {
  const context = useContext(PlaceContext)
  if (!context) throw new Error('usePlace must be used inside PlaceProvider')
  return context
}
