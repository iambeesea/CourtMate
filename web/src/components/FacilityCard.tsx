import { MapPin } from 'lucide-react'
import { Link } from 'react-router'
import { formatDistance, peso, placeLine, plural } from '../lib/format'
import type { FacilitySummary } from '../lib/types'
import { SportIcon } from './SportIcon'
import { DemoBadge } from './StateViews'

export function FacilityCard({ facility, sportId }: { facility: FacilitySummary; sportId?: string }) {
  const href = `/venues/${facility.slug}${sportId ? `?sport=${sportId}` : ''}`
  return (
    <Link to={href} className="card facility-card">
      <div className="card-top">
        <span className="sport-badge">{plural(facility.resourceCount, 'bookable space')}</span>
        {facility.isDemo && <DemoBadge />}
      </div>
      <h3>{facility.name}</h3>
      <p className="meta-line">
        <MapPin size={15} /> {placeLine(facility.location)}
      </p>
      <div className="sport-strip">
        {facility.sports.slice(0, 6).map((sport) => (
          <span key={sport.id} title={sport.name} className={sport.id === sportId ? 'active' : ''}>
            <SportIcon sport={sport} size="sm" />
          </span>
        ))}
        {facility.sports.length > 6 && <small>+{facility.sports.length - 6}</small>}
      </div>
      <div className="card-foot">
        <strong>{facility.fromRateCentavos === null ? 'Rates on request' : facility.fromRateCentavos === 0 ? 'Free to book' : `From ${peso(facility.fromRateCentavos)}/hr`}</strong>
        {facility.distanceKm !== null && <span>{formatDistance(facility.distanceKm)}</span>}
      </div>
    </Link>
  )
}
