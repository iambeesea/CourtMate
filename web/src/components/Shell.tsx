import { ArrowRight, CalendarCheck, ChevronDown, CircleUserRound, Compass, LogIn, MapPin, Plus, Sparkles, Zap } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, NavLink } from 'react-router'
import { useAuth } from '../state/auth'
import { placeLabel, usePlace } from '../state/place'
import { Avatar } from './StateViews'

export function Logo() {
  return (
    <Link to="/" className="brand" aria-label="CourtMate home">
      <span className="brand-mark">
        <span />
      </span>
      <span>
        Court<span>Mate</span>
      </span>
    </Link>
  )
}

const NAV = [
  { to: '/', label: 'Explore', icon: Compass, end: true },
  { to: '/bookings', label: 'Bookings', icon: CalendarCheck, end: false },
  { to: '/play', label: 'Play', icon: Zap, end: false },
  { to: '/profile', label: 'Profile', icon: CircleUserRound, end: false },
]

function Sidebar() {
  const { user, openAuth } = useAuth()
  return (
    <aside className="sidebar">
      <Logo />
      <nav aria-label="Main navigation">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end} className={({ isActive }) => (isActive ? 'active' : '')}>
            <Icon size={20} /> {label}
          </NavLink>
        ))}
      </nav>
      <div className="sidebar-callout">
        <span>
          <Sparkles size={17} />
        </span>
        <strong>Host an open play</strong>
        <p>Bring your community together and manage every queue.</p>
        <Link to="/host">
          Create session <ArrowRight size={15} />
        </Link>
      </div>
      {user ? (
        <Link to="/profile" className="sidebar-user">
          <Avatar user={user} size={36} />
          <div>
            <strong>{user.displayName}</strong>
            <span>{user.isDemo ? 'Demo account' : (user.city?.name ?? 'Add your city')}</span>
          </div>
        </Link>
      ) : (
        <button className="sidebar-user sidebar-signin" onClick={() => openAuth()}>
          <span className="avatar avatar-empty">
            <LogIn size={17} />
          </span>
          <div>
            <strong>Sign in</strong>
            <span>Book, join and track your games</span>
          </div>
        </button>
      )}
    </aside>
  )
}

function Topbar() {
  const { user, openAuth } = useAuth()
  const { place, openPicker } = usePlace()
  return (
    <header className="topbar">
      <div className="mobile-logo">
        <Logo />
      </div>
      <button className="location-pill" onClick={openPicker} aria-label={`Location: ${placeLabel(place)}. Change`}>
        <MapPin size={16} /> <span>{placeLabel(place)}</span> <ChevronDown size={15} />
      </button>
      <div className="topbar-actions">
        <Link to="/host" className="host-button">
          <Plus size={17} /> Host a session
        </Link>
        {user ? (
          <Link to="/profile" aria-label="Your profile">
            <Avatar user={user} />
          </Link>
        ) : (
          <button className="button button-primary button-small" onClick={() => openAuth()}>
            Sign in
          </button>
        )}
      </div>
    </header>
  )
}

function MobileNav() {
  return (
    <nav className="mobile-nav" aria-label="Main navigation">
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={to} end={end} className={({ isActive }) => (isActive ? 'active' : '')}>
          <Icon size={21} />
          <span>{label}</span>
        </NavLink>
      ))}
    </nav>
  )
}

export function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="app-main">
        <Topbar />
        <main>{children}</main>
        <MobileNav />
      </div>
    </div>
  )
}
