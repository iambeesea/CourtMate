import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  Award,
  BarChart3,
  CalendarDays,
  Check,
  ChevronDown,
  CircleUserRound,
  Clock3,
  Download,
  Flame,
  Home,
  MapPin,
  Medal,
  Plus,
  Search,
  Share2,
  Sparkles,
  Trophy,
  UsersRound,
  X,
  Zap,
} from "lucide-react";
import { getPlayerStats, getSessions, joinSession, leaveSession } from "./api";
import { demoStats } from "./data";
import type { PlayerStats, Session, Sport } from "./types";
import "./App.css";

type Tab = "discover" | "sessions" | "stats" | "profile";
const peso = new Intl.NumberFormat("en-PH", {
  style: "currency",
  currency: "PHP",
  maximumFractionDigits: 0,
});

function App() {
  const [tab, setTab] = useState<Tab>("discover");
  const [sport, setSport] = useState<"All" | Sport>("All");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [stats, setStats] = useState<PlayerStats>(demoStats);
  const [loading, setLoading] = useState(true);
  const [storyOpen, setStoryOpen] = useState(false);
  const [toast, setToast] = useState("");

  useEffect(() => {
    Promise.all([getSessions(), getPlayerStats()]).then(
      ([sessionData, statData]) => {
        setSessions(sessionData);
        setStats(statData);
        setLoading(false);
      },
    );
  }, []);

  const filtered = useMemo(
    () =>
      sessions.filter((session) => sport === "All" || session.sport === sport),
    [sessions, sport],
  );

  function showToast(message: string) {
    setToast(message);
    window.setTimeout(() => setToast(""), 2600);
  }

  async function handleJoin(session: Session) {
    const apiSession = session.isJoined
      ? await leaveSession(session.id)
      : await joinSession(session.id);
    setSessions((current) =>
      current.map((item) => {
        if (item.id !== session.id) return item;
        if (apiSession) return apiSession;
        const full = item.joined >= item.capacity;
        return {
          ...item,
          isJoined: !item.isJoined,
          joined: item.isJoined
            ? Math.max(0, item.joined - 1)
            : full
              ? item.joined
              : item.joined + 1,
          waitlist: item.isJoined
            ? Math.max(0, item.waitlist - (full ? 1 : 0))
            : full
              ? item.waitlist + 1
              : item.waitlist,
        };
      }),
    );
    const full = session.joined >= session.capacity;
    showToast(
      session.isJoined
        ? "You left the session."
        : full
          ? "You’re on the waitlist!"
          : "Your spot is confirmed!",
    );
  }

  return (
    <div className="app-shell">
      <Sidebar active={tab} onChange={setTab} />
      <div className="app-main">
        <Header />
        <main>
          {tab === "discover" && (
            <Discover
              sport={sport}
              onSportChange={setSport}
              sessions={filtered}
              loading={loading}
              onJoin={handleJoin}
              onSeeSessions={() => setTab("sessions")}
            />
          )}
          {tab === "sessions" && (
            <MySessions sessions={sessions} onJoin={handleJoin} />
          )}
          {tab === "stats" && (
            <Stats stats={stats} onShare={() => setStoryOpen(true)} />
          )}
          {tab === "profile" && <Profile stats={stats} />}
        </main>
        <MobileNav active={tab} onChange={setTab} />
      </div>
      {storyOpen && (
        <StoryModal stats={stats} onClose={() => setStoryOpen(false)} />
      )}
      {toast && (
        <div className="toast">
          <Check size={17} /> {toast}
        </div>
      )}
    </div>
  );
}

function Logo() {
  return (
    <div className="brand" aria-label="CourtMate home">
      <span className="brand-mark">
        <span />
      </span>
      <span>
        Court<span>Mate</span>
      </span>
    </div>
  );
}

const tabs: Array<{ id: Tab; label: string; icon: typeof Home }> = [
  { id: "discover", label: "Discover", icon: Home },
  { id: "sessions", label: "My sessions", icon: CalendarDays },
  { id: "stats", label: "Player record", icon: BarChart3 },
  { id: "profile", label: "Profile", icon: CircleUserRound },
];

function Sidebar({
  active,
  onChange,
}: {
  active: Tab;
  onChange: (tab: Tab) => void;
}) {
  return (
    <aside className="sidebar">
      <Logo />
      <nav aria-label="Main navigation">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            className={active === id ? "active" : ""}
            onClick={() => onChange(id)}
          >
            <Icon size={20} /> {label}
          </button>
        ))}
      </nav>
      <div className="sidebar-callout">
        <span>
          <Sparkles size={17} />
        </span>
        <strong>Host an open play</strong>
        <p>Bring your community together and manage every queue.</p>
        <button onClick={() => onChange("sessions")}>
          Create session <ArrowRight size={15} />
        </button>
      </div>
      <div className="sidebar-user">
        <div className="avatar avatar-demo">DP</div>
        <div>
          <strong>Demo Player</strong>
          <span>3.0 · Metro Area</span>
        </div>
        <ChevronDown size={17} />
      </div>
    </aside>
  );
}

function Header() {
  return (
    <header className="topbar">
      <div className="mobile-logo">
        <Logo />
      </div>
      <button className="location-pill">
        <MapPin size={16} /> Metro Area <ChevronDown size={15} />
      </button>
      <div className="topbar-actions">
        <button className="search-button" aria-label="Search sessions">
          <Search size={19} />
        </button>
        <button className="host-button">
          <Plus size={17} /> Host a session
        </button>
        <div className="avatar avatar-demo">DP</div>
      </div>
    </header>
  );
}

function MobileNav({
  active,
  onChange,
}: {
  active: Tab;
  onChange: (tab: Tab) => void;
}) {
  return (
    <nav className="mobile-nav" aria-label="Mobile navigation">
      {tabs.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          className={active === id ? "active" : ""}
          onClick={() => onChange(id)}
        >
          <Icon size={21} />
          <span>{label.split(" ")[0]}</span>
        </button>
      ))}
    </nav>
  );
}

function Discover({
  sport,
  onSportChange,
  sessions,
  loading,
  onJoin,
  onSeeSessions,
}: {
  sport: "All" | Sport;
  onSportChange: (sport: "All" | Sport) => void;
  sessions: Session[];
  loading: boolean;
  onJoin: (session: Session) => void;
  onSeeSessions: () => void;
}) {
  return (
    <div className="page discover-page">
      <section className="welcome-row">
        <div>
          <span className="eyebrow">SATURDAY, AUGUST 29</span>
          <h1>Find your next game.</h1>
          <p>Open plays near you, with people who match your pace.</p>
        </div>
        <div className="week-streak">
          <Flame size={20} />
          <div>
            <strong>4 week streak</strong>
            <span>Keep showing up!</span>
          </div>
        </div>
      </section>
      <section className="hero-banner">
        <div className="hero-copy">
          <span className="hero-label">PLAY OF THE WEEK</span>
          <h2>
            Sunday Social:
            <br />
            Rally, rotate, repeat.
          </h2>
          <p>
            Beginner-friendly pickleball with coffee after. Three spots left.
          </p>
          <button onClick={onSeeSessions}>
            View open play <ArrowRight size={17} />
          </button>
        </div>
        <div className="court-illustration" aria-hidden="true">
          <div className="court-net" />
          <div className="ball ball-one" />
          <div className="ball ball-two" />
          <div className="paddle paddle-one" />
          <div className="paddle paddle-two" />
        </div>
      </section>
      <section className="section-block">
        <div className="section-heading">
          <div>
            <span className="eyebrow">PLAY NEARBY</span>
            <h2>Open sessions</h2>
          </div>
          <button className="text-button">
            This week <ChevronDown size={16} />
          </button>
        </div>
        <div className="filters">
          {(["All", "Pickleball", "Badminton"] as const).map((item) => (
            <button
              key={item}
              onClick={() => onSportChange(item)}
              className={sport === item ? "active" : ""}
            >
              {item}
            </button>
          ))}
          <button className="filter-more">
            Level <ChevronDown size={15} />
          </button>
          <button className="filter-more">
            Distance <ChevronDown size={15} />
          </button>
        </div>
        <div className="session-grid">
          {loading
            ? [1, 2, 3].map((item) => (
                <div key={item} className="session-card skeleton" />
              ))
            : sessions.map((session) => (
                <SessionCard
                  key={session.id}
                  session={session}
                  onJoin={onJoin}
                />
              ))}
        </div>
      </section>
      <section className="community-strip">
        <div className="community-icon">
          <UsersRound size={26} />
        </div>
        <div>
          <span className="eyebrow">BUILD YOUR CIRCLE</span>
          <h3>Communities make every game better.</h3>
          <p>
            Meet regular partners, find skill-matched sessions, and never play
            alone.
          </p>
        </div>
        <button>
          Explore communities <ArrowRight size={17} />
        </button>
      </section>
    </div>
  );
}

function SessionCard({
  session,
  onJoin,
}: {
  session: Session;
  onJoin: (session: Session) => void;
}) {
  const spots = Math.max(0, session.capacity - session.joined);
  const full = spots === 0;
  return (
    <article className={`session-card accent-${session.accent}`}>
      <div className="card-top">
        <span className="sport-badge">{session.sport}</span>
        <span className="price">{peso.format(session.price)}</span>
      </div>
      <div className="session-title-row">
        <div className="date-tile">
          <span>{session.dayLabel}</span>
          <strong>{new Date(`${session.date}T00:00:00`).getDate()}</strong>
        </div>
        <div>
          <h3>{session.title}</h3>
          <p>{session.organizer}</p>
        </div>
      </div>
      <div className="session-meta">
        <span>
          <Clock3 size={16} />
          {session.time}
        </span>
        <span>
          <MapPin size={16} />
          {session.venue}
        </span>
        <span>
          <Zap size={16} />
          {session.level}
        </span>
      </div>
      <div className="players-row">
        <div className="avatar-stack">
          {session.players.slice(0, 4).map((player) => (
            <span key={player.id} style={{ background: player.color }}>
              {player.initials}
            </span>
          ))}
        </div>
        <span>
          {full
            ? `${session.waitlist} waiting`
            : `${spots} ${spots === 1 ? "spot" : "spots"} left`}
        </span>
      </div>
      <div className="capacity-bar">
        <span
          style={{
            width: `${Math.min(100, (session.joined / session.capacity) * 100)}%`,
          }}
        />
      </div>
      <button
        className={`join-button ${session.isJoined ? "joined" : ""}`}
        onClick={() => onJoin(session)}
      >
        {session.isJoined ? (
          <>
            <Check size={17} /> Joined
          </>
        ) : full ? (
          "Join waitlist"
        ) : (
          "Join open play"
        )}
      </button>
    </article>
  );
}

function MySessions({
  sessions,
  onJoin,
}: {
  sessions: Session[];
  onJoin: (session: Session) => void;
}) {
  const joined = sessions.filter((session) => session.isJoined);
  const display = joined.length
    ? joined
    : sessions.slice(0, 1).map((session) => ({ ...session, isJoined: true }));
  return (
    <div className="page">
      <div className="page-title">
        <span className="eyebrow">YOUR COURT TIME</span>
        <h1>My sessions</h1>
        <p>Everything you’ve joined, hosted, and played.</p>
      </div>
      <div className="summary-cards">
        <MiniSummary
          icon={CalendarDays}
          value={`${display.length}`}
          label="Upcoming"
        />
        <MiniSummary icon={Trophy} value="28" label="Completed" />
        <MiniSummary icon={UsersRound} value="3" label="Communities" />
      </div>
      <section className="section-block">
        <div className="section-heading">
          <h2>Coming up</h2>
          <button className="primary-small">
            <Plus size={16} /> Create session
          </button>
        </div>
        <div className="upcoming-list">
          {display.map((session) => (
            <article className="upcoming-card" key={session.id}>
              <div className="large-date">
                <span>{session.dayLabel}</span>
                <strong>
                  {new Date(`${session.date}T00:00:00`).getDate()}
                </strong>
                <small>SEP</small>
              </div>
              <div className="upcoming-main">
                <span className="sport-badge">{session.sport}</span>
                <h3>{session.title}</h3>
                <p>
                  <Clock3 size={15} /> {session.time}
                </p>
                <p>
                  <MapPin size={15} /> {session.venue}
                </p>
              </div>
              <div className="court-queue">
                <span>QUEUE STATUS</span>
                <strong>You’re confirmed</strong>
                <div className="mini-court">
                  <i />
                  <i />
                  <i />
                  <i />
                </div>
                <small>13 of 16 players</small>
              </div>
              <button
                className="icon-more"
                onClick={() => onJoin(session)}
                aria-label="Leave session"
              >
                •••
              </button>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function MiniSummary({
  icon: Icon,
  value,
  label,
}: {
  icon: typeof CalendarDays;
  value: string;
  label: string;
}) {
  return (
    <div className="mini-summary">
      <span>
        <Icon size={20} />
      </span>
      <strong>{value}</strong>
      <small>{label}</small>
    </div>
  );
}

function Stats({
  stats,
  onShare,
}: {
  stats: PlayerStats;
  onShare: () => void;
}) {
  const values = [12, 18, 15, 22, 17, 28],
    maxBar = Math.max(...values);
  return (
    <div className="page stats-page">
      <div className="page-title stats-title">
        <div>
          <span className="eyebrow">YOUR SEASON</span>
          <h1>Player record</h1>
          <p>Track progress, celebrate wins, and keep your momentum.</p>
        </div>
        <button className="share-button" onClick={onShare}>
          <Share2 size={17} /> Share match card
        </button>
      </div>
      <section className="record-hero">
        <div className="rating-ring">
          <div>
            <span>RATING</span>
            <strong>{stats.rating.toFixed(2)}</strong>
            <small>+0.18 this month</small>
          </div>
        </div>
        <div className="record-copy">
          <span className="eyebrow light">PICKLEBALL · DOUBLES</span>
          <h2>
            Your game is
            <br />
            moving up.
          </h2>
          <p>
            You’ve won four of your last five matches. Consistency looks good on
            you.
          </p>
          <div className="form-row">
            <span>LAST 5</span>
            {stats.recentForm.map((result, index) => (
              <i className={result === "W" ? "win" : "loss"} key={index}>
                {result}
              </i>
            ))}
          </div>
        </div>
        <Trophy className="record-trophy" size={110} strokeWidth={1.1} />
      </section>
      <div className="stat-grid">
        <Stat value={stats.matches} label="Matches played" note="All time" />
        <Stat
          value={stats.wins}
          label="Wins"
          note={`${stats.winRate}% win rate`}
          positive
        />
        <Stat value={stats.losses} label="Losses" note="Keep learning" />
        <Stat
          value={stats.streak}
          label="Current streak"
          note="Personal best"
          positive
        />
      </div>
      <div className="stats-lower">
        <section className="chart-card">
          <div className="section-heading">
            <div>
              <span className="eyebrow">ACTIVITY</span>
              <h3>Matches by month</h3>
            </div>
            <button className="text-button">
              2026 <ChevronDown size={15} />
            </button>
          </div>
          <div className="bar-chart">
            {values.map((value, index) => (
              <div key={value + index}>
                <span
                  className={index === 5 ? "current" : ""}
                  style={{ height: `${(value / maxBar) * 100}%` }}
                />
                <small>
                  {["MAR", "APR", "MAY", "JUN", "JUL", "AUG"][index]}
                </small>
              </div>
            ))}
          </div>
        </section>
        <section className="achievement-card">
          <span className="eyebrow">LATEST BADGE</span>
          <div className="badge-medal">
            <Medal size={35} />
          </div>
          <h3>Hot streak</h3>
          <p>Won four consecutive matches.</p>
          <small>Unlocked Aug 24</small>
        </section>
      </div>
    </div>
  );
}

function Stat({
  value,
  label,
  note,
  positive,
}: {
  value: number;
  label: string;
  note: string;
  positive?: boolean;
}) {
  return (
    <div className="stat-card">
      <strong>{value}</strong>
      <span>{label}</span>
      <small className={positive ? "positive" : ""}>
        {positive && "↗ "}
        {note}
      </small>
    </div>
  );
}

function Profile({ stats }: { stats: PlayerStats }) {
  return (
    <div className="page profile-page">
      <div className="profile-cover">
        <div className="profile-avatar">DP</div>
      </div>
      <div className="profile-intro">
        <div>
          <h1>Demo Player</h1>
          <p>
            <MapPin size={15} /> Metro Area
          </p>
        </div>
        <button>Edit profile</button>
      </div>
      <div className="profile-tags">
        <span>Pickleball · 3.0</span>
        <span>Badminton · Intermediate</span>
        <span>Right-handed</span>
      </div>
      <p className="profile-bio">
        Always game for a good rally. Building community one court at a time. 🏓
      </p>
      <div className="profile-metrics">
        <div>
          <strong>{stats.matches}</strong>
          <span>Matches</span>
        </div>
        <div>
          <strong>{stats.winRate}%</strong>
          <span>Win rate</span>
        </div>
        <div>
          <strong>14</strong>
          <span>Connections</span>
        </div>
      </div>
      <section className="section-block">
        <div className="section-heading">
          <h2>Achievements</h2>
          <button className="text-button">View all</button>
        </div>
        <div className="badge-row">
          <Badge icon={Flame} label="Hot streak" />
          <Badge icon={Award} label="Early bird" />
          <Badge icon={UsersRound} label="Community player" />
        </div>
      </section>
    </div>
  );
}

function Badge({ icon: Icon, label }: { icon: typeof Flame; label: string }) {
  return (
    <div>
      <span>
        <Icon size={23} />
      </span>
      <strong>{label}</strong>
    </div>
  );
}

function StoryModal({
  stats,
  onClose,
}: {
  stats: PlayerStats;
  onClose: () => void;
}) {
  const [sharing, setSharing] = useState(false);

  function createCardCanvas() {
    const canvas = document.createElement("canvas");
    canvas.width = 1080;
    canvas.height = 1920;
    const context = canvas.getContext("2d");
    if (!context) return null;
    context.fillStyle = "#1f3b73";
    context.fillRect(0, 0, 1080, 1920);
    context.fillStyle = "#e0fe2c";
    context.beginPath();
    context.arc(900, 250, 310, 0, Math.PI * 2);
    context.fill();
    context.fillStyle = "#ffffff";
    context.font = "700 52px Arial";
    context.fillText("COURTMATE", 90, 130);
    context.font = "700 98px Arial";
    context.fillText("MATCH", 90, 450);
    context.fillText("RECAP", 90, 555);
    context.fillStyle = "#e0fe2c";
    context.font = "700 210px Arial";
    context.fillText(`${stats.wins}`, 90, 900);
    context.fillStyle = "#ffffff";
    context.font = "600 44px Arial";
    context.fillText("WINS THIS SEASON", 100, 970);
    context.fillStyle = "rgba(255,255,255,.18)";
    context.fillRect(90, 1120, 900, 360);
    context.fillStyle = "#ffffff";
    context.font = "700 62px Arial";
    context.fillText(`${stats.winRate}% WIN RATE`, 150, 1250);
    context.fillText(`${stats.streak} GAME STREAK`, 150, 1360);
    context.fillStyle = "#e0fe2c";
    context.font = "700 42px Arial";
    context.fillText("DEMO PLAYER  ·  PICKLEBALL 3.0", 90, 1720);
    context.fillStyle = "#ffffff";
    context.font = "400 32px Arial";
    context.fillText("Made to play. Built to connect.", 90, 1790);
    return canvas;
  }

  function canvasToBlob(canvas: HTMLCanvasElement) {
    return new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/png", 1),
    );
  }

  function downloadBlob(blob: Blob) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.download = "courtmate-match-recap.png";
    link.href = url;
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function downloadCard() {
    const canvas = createCardCanvas();
    if (!canvas) return;
    const blob = await canvasToBlob(canvas);
    if (blob) downloadBlob(blob);
  }

  async function shareToInstagram() {
    const canvas = createCardCanvas();
    if (!canvas) return;
    setSharing(true);
    const blob = await canvasToBlob(canvas);
    if (!blob) {
      setSharing(false);
      return;
    }
    const file = new File([blob], "courtmate-match-recap.png", {
      type: "image/png",
    });
    const shareData = {
      files: [file],
      title: "My CourtMate Match Recap",
      text: "Made to play. Built to connect. #CourtMate",
    };

    try {
      if (
        typeof navigator.share === "function" &&
        (typeof navigator.canShare !== "function" ||
          navigator.canShare(shareData))
      ) {
        await navigator.share(shareData);
      } else {
        downloadBlob(blob);
      }
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) {
        downloadBlob(blob);
      }
    } finally {
      setSharing(false);
    }
  }
  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="Share match card"
    >
      <div className="story-panel">
        <button className="modal-close" onClick={onClose}>
          <X size={20} />
        </button>
        <div className="story-card">
          <span className="story-brand">COURTMATE</span>
          <div className="story-ball" />
          <p>
            MATCH
            <br />
            RECAP
          </p>
          <strong>{stats.wins}</strong>
          <span>WINS THIS SEASON</span>
          <div className="story-box">
            <b>{stats.winRate}% WIN RATE</b>
            <b>{stats.streak} GAME STREAK</b>
          </div>
          <small>DEMO PLAYER · PICKLEBALL 3.0</small>
        </div>
        <div className="story-actions">
          <h3>Your match card is ready.</h3>
          <p>
            On your phone, choose <strong>Instagram</strong>, then{" "}
            <strong>Stories</strong> from the native share sheet.
          </p>
          <button onClick={shareToInstagram} disabled={sharing}>
            <Share2 size={17} />
            {sharing ? "Preparing story…" : "Share to Instagram Story"}
          </button>
          <button className="download-button" onClick={downloadCard}>
            <Download size={17} /> Download PNG
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;
