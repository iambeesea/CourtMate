import { LocateFixed, MapPin } from 'lucide-react'
import { useState } from 'react'
import { api } from '../lib/api'
import type { Barangay, City, Place, Province } from '../lib/types'
import { useAsync } from '../lib/useAsync'
import { usePlace, type PlaceFilter } from '../state/place'
import { Modal } from './Modal'

const RADII = [5, 10, 25, 50]

function toPlace(item: Place | undefined): Place | undefined {
  return item ? { code: item.code, name: item.name } : undefined
}

export function LocationPicker() {
  const { place, setPlace, closePicker } = usePlace()
  const area = place.mode === 'area' ? place : null
  const [tab, setTab] = useState<'area' | 'nearby'>(place.mode === 'nearby' ? 'nearby' : 'area')
  const [regionCode, setRegionCode] = useState(area?.region.code ?? '')
  const [provinceCode, setProvinceCode] = useState(area?.province?.code ?? '')
  const [cityCode, setCityCode] = useState(area?.city?.code ?? '')
  const [barangayCode, setBarangayCode] = useState(area?.barangay?.code ?? '')
  const [radiusKm, setRadiusKm] = useState(place.mode === 'nearby' ? place.radiusKm : 10)
  const [locating, setLocating] = useState(false)
  const [geoError, setGeoError] = useState('')

  const regions = useAsync(() => api.regions(), [])
  const provinces = useAsync<Province[]>(() => api.provinces(regionCode), [regionCode], Boolean(regionCode))
  const hasProvinces = Boolean(regionCode) && (provinces.data?.length ?? 0) > 0
  // Regions without provinces (NCR) list their cities directly.
  const citiesReady = Boolean(regionCode) && !provinces.loading && (!hasProvinces || Boolean(provinceCode))
  const cities = useAsync<City[]>(
    () => api.cities(hasProvinces ? { provinceCode } : { regionCode }),
    [regionCode, provinceCode, hasProvinces],
    citiesReady,
  )
  const barangays = useAsync<Barangay[]>(() => api.barangays(cityCode), [cityCode], Boolean(cityCode))

  function apply(filter: PlaceFilter) {
    setPlace(filter)
    closePicker()
  }

  function applyArea() {
    const region = toPlace(regions.data?.find((item) => item.code === regionCode))
    if (!region) return apply({ mode: 'all' })
    apply({
      mode: 'area',
      region,
      province: toPlace(provinces.data?.find((item) => item.code === provinceCode)),
      city: toPlace(cities.data?.find((item) => item.code === cityCode)),
      barangay: toPlace(barangays.data?.find((item) => item.code === barangayCode)),
    })
  }

  function useMyLocation() {
    if (!('geolocation' in navigator)) {
      setGeoError('This device does not share its location with the browser.')
      return
    }
    setLocating(true)
    setGeoError('')
    navigator.geolocation.getCurrentPosition(
      (position) => apply({ mode: 'nearby', lat: position.coords.latitude, lng: position.coords.longitude, radiusKm }),
      () => {
        setLocating(false)
        setGeoError('Location access was not allowed. You can choose an area instead.')
      },
      { enableHighAccuracy: false, timeout: 12000, maximumAge: 300000 },
    )
  }

  return (
    <Modal title="Where do you want to play?" onClose={closePicker}>
      <div className="segmented" role="tablist">
        <button role="tab" aria-selected={tab === 'area'} className={tab === 'area' ? 'active' : ''} onClick={() => setTab('area')}>
          <MapPin size={15} /> Choose an area
        </button>
        <button role="tab" aria-selected={tab === 'nearby'} className={tab === 'nearby' ? 'active' : ''} onClick={() => setTab('nearby')}>
          <LocateFixed size={15} /> Near me
        </button>
      </div>

      {tab === 'area' ? (
        <div className="form">
          <label className="field">
            <span>Region</span>
            <select
              value={regionCode}
              onChange={(event) => {
                setRegionCode(event.target.value)
                setProvinceCode('')
                setCityCode('')
                setBarangayCode('')
              }}
            >
              <option value="">All Philippines</option>
              {regions.data?.map((item) => (
                <option key={item.code} value={item.code}>
                  {item.regionName === item.name ? item.name : `${item.regionName} — ${item.name}`}
                </option>
              ))}
            </select>
          </label>
          {hasProvinces && (
            <label className="field">
              <span>Province</span>
              <select
                value={provinceCode}
                onChange={(event) => {
                  setProvinceCode(event.target.value)
                  setCityCode('')
                  setBarangayCode('')
                }}
              >
                <option value="">All provinces</option>
                {provinces.data?.map((item) => (
                  <option key={item.code} value={item.code}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          {citiesReady && (
            <label className="field">
              <span>City or municipality</span>
              <select
                value={cityCode}
                onChange={(event) => {
                  setCityCode(event.target.value)
                  setBarangayCode('')
                }}
              >
                <option value="">All cities and municipalities</option>
                {cities.data?.map((item) => (
                  <option key={item.code} value={item.code}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          {cityCode && (
            <label className="field">
              <span>Barangay</span>
              <select value={barangayCode} onChange={(event) => setBarangayCode(event.target.value)}>
                <option value="">All barangays</option>
                {barangays.data?.map((item) => (
                  <option key={item.code} value={item.code}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          {regions.error && <p className="form-error">{regions.error.message}</p>}
          <div className="button-row">
            <button className="button button-primary" onClick={applyArea}>
              Show results
            </button>
            <button className="button button-ghost" onClick={() => apply({ mode: 'all' })}>
              All Philippines
            </button>
          </div>
        </div>
      ) : (
        <div className="form">
          <div className="field">
            <span>Search radius</span>
            <div className="chip-row">
              {RADII.map((value) => (
                <button key={value} className={`chip ${radiusKm === value ? 'active' : ''}`} onClick={() => setRadiusKm(value)}>
                  {value} km
                </button>
              ))}
            </div>
          </div>
          <p className="form-hint">Your location is used only to sort and filter results. It is not saved to your account.</p>
          {geoError && (
            <p className="form-error" role="alert">
              {geoError}
            </p>
          )}
          <button className="button button-primary" onClick={useMyLocation} disabled={locating}>
            <LocateFixed size={16} /> {locating ? 'Finding you…' : 'Use my current location'}
          </button>
        </div>
      )}
    </Modal>
  )
}
