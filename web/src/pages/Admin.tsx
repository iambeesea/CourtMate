import { ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { DemoBadge, EmptyState, ErrorState, Loading } from '../components/StateViews'
import { ApiError, api } from '../lib/api'
import { formatMediumDate, placeLine, plural } from '../lib/format'
import type { AdminFacility, VerificationStatus } from '../lib/types'
import { useAsync } from '../lib/useAsync'
import { useAuth } from '../state/auth'
import { useToast } from '../state/toast'

const TABS: VerificationStatus[] = ['pending', 'verified', 'suspended', 'rejected']

/** Facility verification for CourtMate administrators. */
export function Admin() {
  const { user, ready } = useAuth()
  const notify = useToast()
  const [status, setStatus] = useState<VerificationStatus>('pending')
  const isAdmin = user?.role === 'admin'
  const facilities = useAsync(() => api.adminFacilities(status), [status, user?.id], isAdmin)
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)

  if (!ready) return <Loading />
  if (!isAdmin) {
    return (
      <div className="page">
        <EmptyState icon={<ShieldCheck size={24} />} title="Administrators only">
          This page is for reviewing venues before they are listed.
        </EmptyState>
      </div>
    )
  }

  async function decide(facility: AdminFacility, next: VerificationStatus) {
    setBusy(true)
    try {
      await api.verifyFacility(facility.id, next, (notes[facility.id] ?? '').trim())
      notify(`${facility.name} is now ${next}.`)
      facilities.reload()
    } catch (error) {
      notify(error instanceof ApiError ? error.message : 'That didn’t work.', 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page">
      <div className="page-title">
        <span className="eyebrow">ADMINISTRATION</span>
        <h1>Venue verification</h1>
        <p>Only verified venues are listed and bookable. Check the operator’s details before approving.</p>
      </div>
      <div className="segmented" role="tablist">
        {TABS.map((value) => (
          <button key={value} role="tab" aria-selected={status === value} className={status === value ? 'active' : ''} onClick={() => setStatus(value)}>
            {value[0].toUpperCase() + value.slice(1)}
          </button>
        ))}
      </div>
      {facilities.error && !facilities.data ? (
        <ErrorState error={facilities.error} onRetry={facilities.reload} />
      ) : !facilities.data ? (
        <Loading />
      ) : facilities.data.length === 0 ? (
        <p className="notice">No {status} venues.</p>
      ) : (
        <div className="upcoming-list">
          {facilities.data.map((facility) => (
            <article key={facility.id} className="review-card">
              <div className="badge-line">
                <span className="sport-badge">{plural(facility.resourceCount, 'space')}</span>
                {facility.isDemo && <DemoBadge />}
              </div>
              <h3>{facility.name}</h3>
              <p className="meta-line">{[facility.addressLine, placeLine(facility.location), facility.location.region.name].filter(Boolean).join(' · ')}</p>
              <p className="meta-line">
                Registered {formatMediumDate(facility.createdAt)} by {facility.owner.displayName} · {facility.sports.map((sport) => sport.name).join(', ')}
              </p>
              <dl className="contact-list">
                <dt>Contact</dt>
                <dd>{facility.contactName || '—'}</dd>
                <dt>Email</dt>
                <dd>{facility.contactEmail || '—'}</dd>
                <dt>Phone</dt>
                <dd>{facility.contactPhone || '—'}</dd>
              </dl>
              {facility.description && <p className="venue-description">{facility.description}</p>}
              <label className="field">
                <span>Note to the operator</span>
                <input
                  value={notes[facility.id] ?? facility.verificationNotes}
                  onChange={(event) => setNotes((current) => ({ ...current, [facility.id]: event.target.value }))}
                  maxLength={1000}
                />
              </label>
              <div className="button-row">
                {status !== 'verified' && (
                  <button className="button button-primary button-small" disabled={busy} onClick={() => decide(facility, 'verified')}>
                    Verify and list
                  </button>
                )}
                {status === 'pending' && (
                  <button className="button button-ghost button-small" disabled={busy} onClick={() => decide(facility, 'rejected')}>
                    Reject
                  </button>
                )}
                {status === 'verified' && (
                  <button className="button button-ghost button-small" disabled={busy} onClick={() => decide(facility, 'suspended')}>
                    Suspend
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
