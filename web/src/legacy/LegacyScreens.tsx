// The original MVP screens, kept working until the database-backed sessions and
// statistics replace them later on this branch.
import { useState } from "react";
import { CalendarDays, Check, ChevronDown, Clock3, Download, MapPin, Medal, Plus, Share2, Trophy, UsersRound, X, Zap } from "lucide-react";
import type { PlayerStats, Session } from "./types";

const peso = new Intl.NumberFormat("en-PH", {
  style: "currency",
  currency: "PHP",
  maximumFractionDigits: 0,
});

export function SessionCard({
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

export function MySessions({
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

export function Stats({
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

export function StoryModal({
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

