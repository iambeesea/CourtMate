import { Compass } from 'lucide-react'
import { Link, Navigate, Route, Routes, useLocation } from 'react-router'
import { useEffect } from 'react'
import { AuthDialog } from './components/AuthDialog'
import { LocationPicker } from './components/LocationPicker'
import { Shell } from './components/Shell'
import { EmptyState } from './components/StateViews'
import { Admin } from './pages/Admin'
import { Bookings } from './pages/Bookings'
import { Communities } from './pages/Communities'
import { CommunityPage } from './pages/CommunityPage'
import { Explore } from './pages/Explore'
import { HostSession } from './pages/HostSession'
import { Notifications } from './pages/Notifications'
import { OperatorFacilityPage, OperatorHome } from './pages/Operator'
import { Play } from './pages/Play'
import { Profile } from './pages/Profile'
import { SessionPage } from './pages/SessionPage'
import { TeamPage } from './pages/TeamPage'
import { Venue } from './pages/Venue'
import { useAuth } from './state/auth'
import { usePlace } from './state/place'
import './styles/legacy.css'
import './styles/app.css'

function ScrollToTop() {
  const { pathname, hash } = useLocation()
  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView()
    else window.scrollTo(0, 0)
  }, [pathname, hash])
  return null
}

function NotFound() {
  return (
    <div className="page">
      <EmptyState
        icon={<Compass size={24} />}
        title="That page isn’t here"
        action={
          <Link to="/" className="button button-primary">
            Back to Explore
          </Link>
        }
      >
        The link may be old, or the page may have moved.
      </EmptyState>
    </div>
  )
}

export default function App() {
  const { dialog } = useAuth()
  const { pickerOpen } = usePlace()
  return (
    <Shell>
      <ScrollToTop />
      <Routes>
        <Route path="/" element={<Explore />} />
        <Route path="/venues/:id" element={<Venue />} />
        <Route path="/bookings" element={<Bookings />} />
        <Route path="/sessions/:id" element={<SessionPage />} />
        <Route path="/host" element={<HostSession />} />
        <Route path="/play" element={<Play />} />
        <Route path="/communities" element={<Communities />} />
        <Route path="/communities/:id" element={<CommunityPage />} />
        <Route path="/teams/:id" element={<TeamPage />} />
        <Route path="/notifications" element={<Notifications />} />
        <Route path="/operator" element={<OperatorHome />} />
        <Route path="/operator/:id" element={<OperatorFacilityPage />} />
        <Route path="/admin" element={<Admin />} />
        <Route path="/record" element={<Navigate to="/profile" replace />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
      {dialog && <AuthDialog key={dialog.mode} />}
      {pickerOpen && <LocationPicker />}
    </Shell>
  )
}
