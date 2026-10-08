import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useMemo } from 'react'
import { MapContainer, Marker, Popup, TileLayer, useMap } from 'react-leaflet'
import { Link } from 'react-router'

export interface MapPoint {
  id: string
  latitude: number
  longitude: number
  title: string
  subtitle?: string
  href?: string
  tone?: 'venue' | 'session'
}

// OpenStreetMap's public tiles are fine for development and light use; set VITE_MAP_TILE_URL to a provider for production traffic.
const TILE_URL = import.meta.env.VITE_MAP_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
const ATTRIBUTION = import.meta.env.VITE_MAP_ATTRIBUTION || '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
const PHILIPPINES: L.LatLngBoundsExpression = [
  [4.5, 116.5],
  [21.2, 127],
]

function pin(tone: MapPoint['tone']) {
  return L.divIcon({ className: '', html: `<span class="map-pin map-pin-${tone ?? 'venue'}"></span>`, iconSize: [26, 26], iconAnchor: [13, 24], popupAnchor: [0, -22] })
}

function FitToPoints({ points, origin }: { points: MapPoint[]; origin?: [number, number] }) {
  const map = useMap()
  useEffect(() => {
    const coordinates: Array<[number, number]> = points.map((point) => [point.latitude, point.longitude])
    if (origin) coordinates.push(origin)
    if (coordinates.length === 0) map.fitBounds(PHILIPPINES)
    else if (coordinates.length === 1) map.setView(coordinates[0], 14)
    else map.fitBounds(coordinates, { padding: [36, 36], maxZoom: 15 })
  }, [map, points, origin])
  return null
}

export default function MapView({ points, origin, height = 420 }: { points: MapPoint[]; origin?: [number, number]; height?: number }) {
  const icons = useMemo(() => ({ venue: pin('venue'), session: pin('session') }), [])
  return (
    <div className="map-frame" style={{ height }}>
      <MapContainer bounds={PHILIPPINES} scrollWheelZoom={false} style={{ height: '100%', width: '100%' }}>
        <TileLayer url={TILE_URL} attribution={ATTRIBUTION} />
        <FitToPoints points={points} origin={origin} />
        {origin && <Marker position={origin} icon={L.divIcon({ className: '', html: '<span class="map-you"></span>', iconSize: [18, 18], iconAnchor: [9, 9] })} />}
        {points.map((point) => (
          <Marker key={point.id} position={[point.latitude, point.longitude]} icon={icons[point.tone ?? 'venue']}>
            <Popup>
              <strong>{point.title}</strong>
              {point.subtitle && <span className="map-popup-sub">{point.subtitle}</span>}
              {point.href && (
                <Link to={point.href} className="map-popup-link">
                  View details
                </Link>
              )}
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  )
}
