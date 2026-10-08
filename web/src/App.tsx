import { Compass } from 'lucide-react'
import { Link, Route, Routes, useLocation } from 'react-router'
import { useEffect } from 'react'
import { AuthDialog } from './components/AuthDialog'
import { LocationPicker } from './components/LocationPicker'
import { Shell } from './components/Shell'
import { EmptyState } from './components/StateViews'
import { Bookings } from './pages/Bookings'
import { Explore } from './pages/Explore'
import { LegacyPlay, LegacyRecord } from './pages/LegacyPages'
import { Profile } from './pages/Profile'
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
        <Route path="/play" element={<LegacyPlay />} />
        <Route path="/record" element={<LegacyRecord />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
      {dialog && <AuthDialog key={dialog.mode} />}
      {pickerOpen && <LocationPicker />}
    </Shell>
  )
}
