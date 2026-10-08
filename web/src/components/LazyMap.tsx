import { lazy, Suspense } from 'react'
import type { MapPoint } from './MapView'
import { Loading } from './StateViews'

// Leaflet is only downloaded when a map is actually shown.
const MapView = lazy(() => import('./MapView'))

export function LazyMap(props: { points: MapPoint[]; origin?: [number, number]; height?: number }) {
  return (
    <Suspense fallback={<Loading label="Loading map…" />}>
      <MapView {...props} />
    </Suspense>
  )
}
