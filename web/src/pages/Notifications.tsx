import { Bell } from 'lucide-react'
import { useEffect } from 'react'
import { Link } from 'react-router'
import { EmptyState, ErrorState, Loading } from '../components/StateViews'
import { api } from '../lib/api'
import { formatMediumDate, formatTime } from '../lib/format'
import { useAsync } from '../lib/useAsync'
import { useAuth } from '../state/auth'
import { useNotifications } from '../state/notifications'

export function Notifications() {
  const { user, ready, openAuth } = useAuth()
  const { refresh } = useNotifications()
  const inbox = useAsync(() => api.notifications(), [user?.id], Boolean(user))
  const unread = inbox.data?.unread ?? 0

  // Opening the page is what marks things read; the list keeps its unread styling for this visit.
  useEffect(() => {
    if (unread > 0) void api.markNotificationsRead().then(refresh, () => undefined)
  }, [unread, refresh])

  if (!ready) return <Loading />
  if (!user) {
    return (
      <div className="page">
        <EmptyState
          icon={<Bell size={24} />}
          title="Notifications"
          action={
            <button className="button button-primary" onClick={() => openAuth()}>
              Sign in
            </button>
          }
        >
          Sign in to see updates about your sessions and bookings.
        </EmptyState>
      </div>
    )
  }

  return (
    <div className="page profile-page">
      <div className="page-title">
        <span className="eyebrow">UPDATES</span>
        <h1>Notifications</h1>
        <p>Waitlist moves, host decisions, schedule changes and booking updates.</p>
      </div>
      {inbox.error && !inbox.data ? (
        <ErrorState error={inbox.error} onRetry={inbox.reload} />
      ) : !inbox.data ? (
        <Loading />
      ) : inbox.data.items.length === 0 ? (
        <EmptyState icon={<Bell size={24} />} title="You’re all caught up">
          When something changes in a session or booking you’re part of, it shows up here.
        </EmptyState>
      ) : (
        <div className="link-list">
          {inbox.data.items.map((item) => {
            const body = (
              <>
                <Bell size={20} />
                <div>
                  <strong>{item.title}</strong>
                  <span>{item.body}</span>
                  <small>
                    {formatMediumDate(item.createdAt)}, {formatTime(item.createdAt)}
                  </small>
                </div>
              </>
            )
            const className = `link-row ${item.readAt ? '' : 'unread'}`
            return item.link ? (
              <Link key={item.id} to={item.link} className={className}>
                {body}
              </Link>
            ) : (
              <div key={item.id} className={className}>
                {body}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
