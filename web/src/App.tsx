import { Compass } from 'lucide-react'
import { Link, Navigate, Route, Routes, useLocation } from 'react-router'
import { lazy, Suspense, useEffect } from 'react'
import { AuthDialog } from './components/AuthDialog'
import { LocationPicker } from './components/LocationPicker'
import { Shell } from './components/Shell'
import { EmptyState, Loading } from './components/StateViews'
import { Bookings } from './pages/Bookings'
import { Explore } from './pages/Explore'
import { Play } from './pages/Play'
import { Profile } from './pages/Profile'
import { SessionPage } from './pages/SessionPage'
import { Venue } from './pages/Venue'
import { useAuth } from './state/auth'
import { usePlace } from './state/place'
import './styles/legacy.css'
import './styles/app.css'

// Screens most visitors never open are split out of the first download.
const Admin = lazy(() => import('./pages/Admin').then((module) => ({ default: module.Admin })))
const Communities = lazy(() => import('./pages/Communities').then((module) => ({ default: module.Communities })))
const CommunityPage = lazy(() => import('./pages/CommunityPage').then((module) => ({ default: module.CommunityPage })))
const HostSession = lazy(() => import('./pages/HostSession').then((module) => ({ default: module.HostSession })))
const Notifications = lazy(() => import('./pages/Notifications').then((module) => ({ default: module.Notifications })))
const OperatorFacilityPage = lazy(() => import('./pages/Operator').then((module) => ({ default: module.OperatorFacilityPage })))
const OperatorHome = lazy(() => import('./pages/Operator').then((module) => ({ default: module.OperatorHome })))
const TeamPage = lazy(() => import('./pages/TeamPage').then((module) => ({ default: module.TeamPage })))

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
      <Suspense fallback={<Loading />}>
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
      </Suspense>
      {dialog && <AuthDialog key={dialog.mode} />}
      {pickerOpen && <LocationPicker />}
    </Shell>
  )
}
