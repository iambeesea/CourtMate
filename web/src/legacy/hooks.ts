import { useEffect, useState } from "react";
import { getPlayerStats, getSessions, joinSession, leaveSession } from "./api";
import { demoStats } from "./data";
import type { PlayerStats, Session } from "./types";

export function useLegacySessions(notify: (message: string) => void) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getSessions().then((data) => {
      setSessions(data);
      setLoading(false);
    });
  }, []);

  async function toggle(session: Session) {
    const apiSession = session.isJoined ? await leaveSession(session.id) : await joinSession(session.id);
    const full = session.joined >= session.capacity;
    setSessions((current) =>
      current.map((item) => {
        if (item.id !== session.id) return item;
        if (apiSession) return apiSession;
        return {
          ...item,
          isJoined: !item.isJoined,
          joined: item.isJoined ? Math.max(0, item.joined - 1) : full ? item.joined : item.joined + 1,
          waitlist: item.isJoined ? Math.max(0, item.waitlist - (full ? 1 : 0)) : full ? item.waitlist + 1 : item.waitlist,
        };
      }),
    );
    notify(session.isJoined ? "You left the session." : full ? "You’re on the waitlist!" : "Your spot is confirmed!");
  }

  return { sessions, loading, toggle };
}

export function useLegacyStats() {
  const [stats, setStats] = useState<PlayerStats>(demoStats);
  useEffect(() => {
    getPlayerStats().then(setStats);
  }, []);
  return stats;
}
